package org.pregacao.controle

import org.eclipse.paho.client.mqttv3.IMqttDeliveryToken
import org.eclipse.paho.client.mqttv3.MqttCallbackExtended
import org.eclipse.paho.client.mqttv3.MqttConnectOptions
import org.eclipse.paho.client.mqttv3.MqttMessage
import org.eclipse.paho.client.mqttv3.persist.MemoryPersistence
import org.eclipse.paho.client.mqttv3.MqttAsyncClient
import java.util.UUID
import javax.net.ssl.SSLSocketFactory

/**
 * Ponte MQTT com o equipamento.
 *
 * O APK e apenas um observador com dois botoes: assina
 * `pregacao/<id>/{avail,state,events,ack}` e publica em
 * `pregacao/<id>/cmd`. Audio nunca trafega por aqui.
 *
 * Reconexao automatica e feita pelo proprio paho (isAutomaticReconnect):
 * se a Internet do celular cair e voltar, a tela volta a atualizar sem
 * o operador precisar fazer nada.
 */
class MqttController(
    private val servidor: String,
    private val porta: Int,
    private val tls: Boolean,
    private val aparelho: String,
    private val usuario: String,
    private val token: String,
    private val callbacks: Callbacks,
) {

    /** Eventos que a tela precisa saber (chamados na thread do paho). */
    interface Callbacks {
        fun conectado(ok: Boolean, detalhe: String)
        fun disponibilidade(online: Boolean)
        fun estado(retido: Boolean, json: String)
        fun ack(json: String)
        fun evento(json: String)
        fun comandoEnviado(ok: Boolean, detalhe: String)
    }

    private val raiz = "pregacao/$aparelho"
    private var client: MqttAsyncClient? = null

    /** URL do broker: ssl:// (TLS) ou tcp:// (somente para teste local). */
    private val url: String
        get() = (if (tls) "ssl://" else "tcp://") + servidor + ":" + porta

    fun conectar() {
        val clientId = "apk-" + UUID.randomUUID().toString().substring(0, 8)
        val mqtt = MqttAsyncClient(url, clientId, MemoryPersistence())

        mqtt.setCallback(object : MqttCallbackExtended {
            override fun connectComplete(reconnect: Boolean, serverURI: String?) {
                assinar(mqtt)
                callbacks.conectado(true, if (reconnect) "reconectado" else "conectado")
            }

            override fun connectionLost(cause: Throwable?) {
                callbacks.conectado(false, cause?.message ?: "conexao perdida")
            }

            override fun messageArrived(topic: String?, message: MqttMessage?) {
                val payload = String(message?.payload ?: ByteArray(0), Charsets.UTF_8)
                when {
                    topic == null -> Unit
                    topic.endsWith("/avail") ->
                        callbacks.disponibilidade(payload.trim() == "online")
                    topic.endsWith("/state") ->
                        callbacks.estado(message?.isRetained == true, payload)
                    topic.endsWith("/ack") -> callbacks.ack(payload)
                    topic.endsWith("/events") -> callbacks.evento(payload)
                }
            }

            override fun deliveryComplete(token: IMqttDeliveryToken?) = Unit
        })

        val opcoes = MqttConnectOptions().apply {
            isAutomaticReconnect = true
            isCleanSession = true
            keepAliveInterval = 60
            connectionTimeout = 15
            if (usuario.isNotBlank()) userName = usuario
            if (token.isNotBlank()) password = token.toCharArray()
            if (tls) socketFactory = SSLSocketFactory.getDefault() as SSLSocketFactory
        }

        try {
            mqtt.connect(opcoes, null, object : org.eclipse.paho.client.mqttv3.IMqttActionListener {
                override fun onSuccess(asyncActionToken: org.eclipse.paho.client.mqttv3.IMqttToken?) = Unit

                override fun onFailure(
                    asyncActionToken: org.eclipse.paho.client.mqttv3.IMqttToken?,
                    exception: Throwable?,
                ) {
                    callbacks.conectado(false, traduzirFalha(exception))
                }
            })
            client = mqtt
        } catch (exc: Exception) {
            callbacks.conectado(false, traduzirFalha(exc))
        }
    }

    /**
     * Converte a excecao crua do paho em algo que o operador consiga usar.
     *
     * O paho devolve "Not authorized" (ou o texto que o broker mandar) sem
     * dizer o que fazer - e a causa quase sempre e o token, nao a rede. Aqui
     * a recusa de credencial vira uma frase que aponta para Configuracoes;
     * o resto mantem o texto original, que ainda ajuda a diagnosticar.
     */
    private fun traduzirFalha(exc: Throwable?): String {
        val cadeia = generateSequence(exc) { it.cause }.toList()

        val recusa = cadeia.any { item ->
            (item is org.eclipse.paho.client.mqttv3.MqttException &&
                item.reasonCode in CODIGOS_CREDENCIAL) ||
                item.message?.let { msg ->
                    PALAVRAS_CREDENCIAL.any { msg.contains(it, ignoreCase = true) }
                } == true
        }
        if (recusa) return MSG_CREDENCIAL

        val alcancavel = cadeia.any { item ->
            item.message?.let { msg ->
                PALAVRAS_REDE.any { msg.contains(it, ignoreCase = true) }
            } == true
        }
        if (alcancavel) return MSG_REDE

        return exc?.message ?: "falha ao conectar"
    }

    private fun assinar(mqtt: MqttAsyncClient) {
        listOf("avail", "state", "ack", "events").forEach { sufixo ->
            try {
                mqtt.subscribe("$raiz/$sufixo", 1)
            } catch (exc: Exception) {
                callbacks.conectado(false, "falha ao assinar $sufixo: ${exc.message}")
            }
        }
    }

    /**
     * Envia um comando com `req_id` proprio (o equipamento devolve o mesmo
     * valor no ack - e o que permite saber qual resposta pertence a qual
     * botao).
     *
     * `extras` carrega argumentos de Drive e destino de gravacao.
     * O payload e montado por `JSONObject`, e nao com string pronta, porque
     * a senha do Wi-Fi pode ter aspas ou barra invertida e JSON montado na
     * mao quebraria no meio (ou enviaria a senha cortada).
     */
    fun enviar(cmd: String, extras: Map<String, String> = emptyMap()): String {
        val reqId = "apk-" + System.currentTimeMillis()
        val payload = try {
            org.json.JSONObject().apply {
                put("cmd", cmd)
                put("req_id", reqId)
                extras.forEach { (chave, valor) -> put(chave, valor) }
            }.toString()
        } catch (exc: Exception) {
            callbacks.comandoEnviado(
                false, "falha ao montar o comando: " + (exc.message ?: "erro")
            )
            return reqId
        }
        val mqtt = client
        if (mqtt?.isConnected != true) {
            callbacks.comandoEnviado(false, "sem conexao com o equipamento")
            return reqId
        }
        try {
            val msg = MqttMessage(payload.toByteArray(Charsets.UTF_8)).apply {
                qos = 1
                isRetained = false
            }
            mqtt.publish("$raiz/cmd", msg, null, object : org.eclipse.paho.client.mqttv3.IMqttActionListener {
                override fun onSuccess(asyncActionToken: org.eclipse.paho.client.mqttv3.IMqttToken?) =
                    callbacks.comandoEnviado(true, cmd)

                override fun onFailure(
                    asyncActionToken: org.eclipse.paho.client.mqttv3.IMqttToken?,
                    exception: Throwable?,
                ) {
                    callbacks.comandoEnviado(false, exception?.message ?: "falha ao enviar")
                }
            })
        } catch (exc: Exception) {
            callbacks.comandoEnviado(false, exc.message ?: "falha ao enviar")
        }
        return reqId
    }

    fun desconectar() {
        try {
            client?.disconnect()
        } catch (_: Exception) {
            // nada a fazer: a conexao ja caiu
        }
        client = null
    }

    private companion object {
        // paho 1.2.5: 4 = senha invalida, 5 = nao autorizado (CONNACK)
        val CODIGOS_CREDENCIAL = setOf(4, 5)

        // cobre o texto do paho e o que o broker devolver, em ingles ou nao
        val PALAVRAS_CREDENCIAL = listOf(
            "not authorized", "authoriz", "autoriz",
            "bad user", "authentication", "autentic",
            "password", "senha",
        )

        val PALAVRAS_REDE = listOf(
            "timeout", "timed out", "unreachable", "inacess",
            "unable to connect", "network", "rede",
        )

        const val MSG_CREDENCIAL =
            "Broker recusou o usuario/token. Confira em Configuracoes: " +
                "usuario 'operador' + token do painel."

        const val MSG_REDE =
            "Sem conexao com o servidor. Verifique a Internet do celular."
    }
}
