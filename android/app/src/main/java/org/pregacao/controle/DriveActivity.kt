package org.pregacao.controle

import android.app.AlertDialog
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.widget.Button
import android.widget.TextView
import android.widget.Toast
import org.json.JSONObject
import java.net.InetSocketAddress
import java.net.ServerSocket
import java.net.Socket
import java.net.URI
import java.net.URLDecoder

/**
 * Conectar a conta Google do equipamento, espelhando o painel do Raspberry.
 *
 * Por que existe um servidor local aqui
 * -------------------------------------
 * O redirect do OAuth e `http://localhost:8080/oauth/callback` porque a
 * credencial e de APLICATIVO DE COMPUTADOR, so aceita loopback - e o Pi nao
 * pode expor porta na rede. No celular, `localhost` e o PROPRIO celular: o
 * navegador do aparelho e' quem recebe o retorno do Google, e este servidor
 * e' quem captura `code` e `state` de la.
 *
 * O segredo NUNCA passa por aqui: o APK devolve o codigo ao equipamento
 * (DRIVE_FINISH) e quem troca pelo token e o Raspberry. O `state` acompanha
 * para que um codigo de outro pedido nao seja aceito.
 *
 * O servidor e' aberto ANTES de acionar o navegador - se a porta nao estiver
 * escutando quando o Google redirecionar, a autorizacao falha no meio.
 */
class DriveActivity : BaseActivity(), MqttController.Callbacks {

    private lateinit var prefs: Prefs
    private var mqtt: MqttController? = null

    private lateinit var txtStatus: TextView
    private lateinit var txtDetalhe: TextView
    private lateinit var txtAviso: TextView
    private lateinit var btnConectar: Button
    private lateinit var btnTestar: Button
    private lateinit var btnDesconectar: Button

    private val handler = Handler(Looper.getMainLooper())

    /** req_id do pedido em andamento. */
    private var pedidoAtual = ""

    /** O que esta pendente: define como o proximo ack e' interpretado. */
    private var pendente = ""

    /** Servidor de retorno local (localhost), aberto so durante o fluxo. */
    private var servidorLocal: ServerSocket? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_drive)
        prefs = Prefs(this)

        txtStatus = findViewById(R.id.txtDriveStatus)
        txtDetalhe = findViewById(R.id.txtDriveDetalhe)
        txtAviso = findViewById(R.id.txtDriveAviso)
        btnConectar = findViewById(R.id.btnConectar)
        btnTestar = findViewById(R.id.btnTestar)
        btnDesconectar = findViewById(R.id.btnDesconectar)

        btnConectar.setOnClickListener { conectarConta() }
        btnTestar.setOnClickListener { testarPasta() }
        btnDesconectar.setOnClickListener { confirmarDesconexao() }

        actionBar?.subtitle = "v" + BuildConfig.VERSION_NAME
    }

    override fun onResume() {
        super.onResume()
        if (mqtt == null) iniciar()
    }

    override fun onStop() {
        super.onStop()
        // o navegador e' uma activity externa: ao voltar, a conexao volta
        mqtt?.desconectar()
        mqtt = null
    }

    override fun onDestroy() {
        fecharServidorLocal()
        handler.removeCallbacksAndMessages(null)
        super.onDestroy()
    }

    // --------------------------------------------------------------
    // conexao
    // --------------------------------------------------------------
    private fun iniciar() {
        if (!prefs.pronto()) {
            txtStatus.setText(R.string.drive_sem_config)
            habilitarBotoes(false)
            return
        }
        txtStatus.setText(R.string.drive_verificando)
        mqtt = MqttController(
            servidor = prefs.servidor,
            porta = prefs.porta,
            tls = prefs.tls,
            aparelho = prefs.aparelho,
            usuario = prefs.usuario,
            token = prefs.token,
            callbacks = this,
        ).also { it.conectar() }
    }

    // --------------------------------------------------------------
    // callbacks do MQTT (chamados fora da thread da UI)
    // --------------------------------------------------------------
    override fun conectado(ok: Boolean, detalhe: String) {
        runOnUiThread {
            if (ok) {
                pedirStatus()
            } else {
                txtStatus.text = detalhe
                habilitarBotoes(false)
            }
        }
    }

    override fun disponibilidade(online: Boolean) = Unit

    override fun estado(retido: Boolean, json: String) = Unit

    override fun evento(json: String) = Unit

    override fun comandoEnviado(ok: Boolean, detalhe: String) {
        runOnUiThread {
            if (ok) return@runOnUiThread
            txtStatus.text = detalhe
            habilitarBotoes(true)
        }
    }

    override fun ack(json: String) {
        runOnUiThread { processarAck(json) }
    }

    // --------------------------------------------------------------
    // respostas do equipamento
    // --------------------------------------------------------------
    private fun processarAck(json: String) {
        val obj = pegar(json) ?: return
        if (obj.optString("req_id", "") != pedidoAtual) return

        val tipo = pendente
        pendente = ""

        if (!obj.optBoolean("ok", false)) {
            fecharServidorLocal()
            txtStatus.text = obj.optString("error", "falha no pedido")
            txtAviso.text = ""
            habilitarBotoes(true)
            return
        }

        when (tipo) {
            "status" -> mostrarStatus(obj.optJSONObject("drive"))

            "connect" -> {
                val url = obj.optString("url", "")
                val redirect = obj.optString("redirect_uri", "")
                if (url.isBlank()) {
                    txtStatus.setText(R.string.drive_sem_configuracao)
                    habilitarBotoes(true)
                    return
                }
                // a porta do retorno vem do equipamento: abrir ANTES do
                // navegador, senao o Google cai num "conexao recusada"
                if (!abrirServidorLocal(portaDo(redirect))) {
                    habilitarBotoes(true)
                    return
                }
                txtStatus.setText(R.string.drive_abrindo)
                txtAviso.setText(R.string.drive_aguardando)
                abrirNavegador(url)
            }

            "finish" -> {
                fecharServidorLocal()
                txtStatus.setText(R.string.drive_conectado_ok)
                txtAviso.text = ""
                habilitarBotoes(true)
                handler.postDelayed({ pedirStatus() }, 800)
            }

            "test" -> {
                val pasta = obj.optString("folder_id", "")
                txtAviso.text = if (pasta.isBlank()) {
                    getString(R.string.drive_testado)
                } else {
                    getString(R.string.drive_testado) + "\n" + pasta
                }
                habilitarBotoes(true)
            }

            "disconnect" -> {
                txtStatus.setText(R.string.drive_desconectado_ok)
                txtAviso.text = ""
                habilitarBotoes(true)
                handler.postDelayed({ pedirStatus() }, 500)
            }
        }
    }

    private fun mostrarStatus(drive: JSONObject?) {
        habilitarBotoes(true)
        txtAviso.text = ""
        if (drive == null) {
            txtStatus.setText(R.string.drive_verificando)
            return
        }

        if (!drive.optBoolean("libraries", false)) {
            txtStatus.setText(R.string.drive_sem_biblioteca)
            txtDetalhe.visibility = android.view.View.GONE
            btnConectar.isEnabled = false
            btnTestar.isEnabled = false
            return
        }
        if (!drive.optBoolean("credentials", false)) {
            txtStatus.setText(R.string.drive_sem_configuracao)
            txtDetalhe.visibility = android.view.View.GONE
            btnTestar.isEnabled = false
            btnDesconectar.isEnabled = false
            return
        }

        val conectado = drive.optBoolean("connected", false)
        val conta = drive.optString("account", "")
        val pasta = drive.optString("folder", "")
        val auto = drive.optBoolean("auto_upload", false)

        if (conectado) {
            txtStatus.text = getString(
                R.string.drive_conectado, conta.ifBlank { "conta Google" }
            )
            val linhas = mutableListOf<String>()
            if (pasta.isNotBlank()) linhas.add(getString(R.string.drive_pasta, pasta))
            linhas.add(
                getString(if (auto) R.string.drive_auto_on else R.string.drive_auto_off)
            )
            txtDetalhe.text = linhas.joinToString("\n")
            txtDetalhe.visibility = android.view.View.VISIBLE
        } else {
            txtStatus.setText(R.string.drive_sem_conta)
            txtDetalhe.visibility = android.view.View.GONE
            btnTestar.isEnabled = false
            btnDesconectar.isEnabled = false
        }
    }

    // --------------------------------------------------------------
    // servidor de retorno local (o navegador entrega o codigo aqui)
    // --------------------------------------------------------------
    /**
     * Abre a porta do loopback e comeca a escutar. Feito de forma SINCRONA
     * de proposito: a chamada retorna com o socket ja' escutando, e so entao
     * o navegador e' aberto - se fosse assincrono o Google poderia
     * redirecionar antes de existir quem escuta.
     */
    private fun abrirServidorLocal(porta: Int): Boolean {
        fecharServidorLocal()
        return try {
            val server = ServerSocket()
            server.reuseAddress = true
            server.bind(InetSocketAddress(LOCALHOST, porta))
            servidorLocal = server
            Thread {
                try {
                    while (!server.isClosed) {
                        val socket = server.accept()
                        try {
                            atender(socket)
                        } catch (_: Exception) {
                            // resposta ja' falhou; o finally fecha o socket
                        } finally {
                            try {
                                socket.close()
                            } catch (_: Exception) {
                                // socket ja' fechado
                            }
                        }
                    }
                } catch (_: Exception) {
                    // servidor fechado no meio da espera: fim normal
                }
            }.apply {
                isDaemon = true
                start()
            }
            true
        } catch (exc: Exception) {
            txtStatus.text = getString(
                R.string.drive_erro_local, porta, exc.message ?: "erro"
            )
            false
        }
    }

    /** Le a requisicao, responde ao navegador e, se for o callback, segue. */
    private fun atender(socket: Socket) {
        val entrada = socket.getInputStream() ?: return
        val buffer = ByteArray(8192)
        val lidos = entrada.read(buffer)
        if (lidos <= 0) return
        val texto = String(buffer, 0, lidos, Charsets.UTF_8)
        val linha = texto.lineSequence().firstOrNull() ?: ""

        // "GET /oauth/callback?code=X&state=Y HTTP/1.1"
        val caminho = linha.split(" ").getOrNull(1) ?: ""
        val consulta = if (caminho.contains("?")) caminho.substringAfter("?") else ""
        val parametros = lerQuery(consulta)
        val codigo = parametros["code"] ?: ""

        if (caminho.startsWith("/oauth/callback") && codigo.isNotBlank()) {
            responder(socket, paginaDeSucesso())
            val state = parametros["state"] ?: ""
            runOnUiThread { finalizarAutorizacao(codigo, state) }
        } else {
            responder(socket, paginaDeErro())
        }
    }

    private fun responder(socket: Socket, html: String) {
        val corpo = html.toByteArray(Charsets.UTF_8)
        val cabecalho = (
            "HTTP/1.1 200 OK\r\n" +
                "Content-Type: text/html; charset=utf-8\r\n" +
                "Content-Length: " + corpo.size + "\r\n" +
                "Connection: close\r\n" +
                "\r\n"
            ).toByteArray(Charsets.US_ASCII)
        val saida = socket.getOutputStream()
        saida.write(cabecalho)
        saida.write(corpo)
        saida.flush()
    }

    private fun fecharServidorLocal() {
        try {
            servidorLocal?.close()
        } catch (_: Exception) {
            // ja' estava fechado
        }
        servidorLocal = null
    }

    private fun lerQuery(consulta: String): Map<String, String> {
        if (consulta.isBlank()) return emptyMap()
        return consulta.split("&").mapNotNull { par ->
            val chave = par.substringBefore("=")
            if (chave.isBlank()) null
            else {
                val valor = par.substringAfter("=", "")
                chave to URLDecoder.decode(valor, "UTF-8")
            }
        }.toMap()
    }

    private fun portaDo(redirect: String): Int = try {
        val porta = URI(redirect).port
        if (porta > 0) porta else PORTA_PADRAO
    } catch (_: Exception) {
        PORTA_PADRAO
    }

    // --------------------------------------------------------------
    // acoes
    // --------------------------------------------------------------
    private fun pedirStatus() {
        pendente = "status"
        pedidoAtual = mqtt?.enviar("DRIVE_STATUS") ?: ""
    }

    private fun conectarConta() {
        habilitarBotoes(false)
        pendente = "connect"
        pedidoAtual = mqtt?.enviar("DRIVE_CONNECT") ?: ""
    }

    private fun finalizarAutorizacao(codigo: String, state: String) {
        // ja' chegou o que precisavamos: parar de escutar a porta
        fecharServidorLocal()
        val extras = mutableMapOf("code" to codigo)
        if (state.isNotBlank()) extras["state"] = state
        pendente = "finish"
        pedidoAtual = mqtt?.enviar("DRIVE_FINISH", extras) ?: ""
    }

    private fun testarPasta() {
        habilitarBotoes(false)
        txtAviso.text = ""
        pendente = "test"
        pedidoAtual = mqtt?.enviar("DRIVE_TEST") ?: ""
    }

    private fun confirmarDesconexao() {
        AlertDialog.Builder(this)
            .setTitle(R.string.drive_confirmar_desconexao)
            .setMessage(R.string.drive_confirmar_msg)
            .setPositiveButton(R.string.drive_desconectar_sim) { _, _ ->
                habilitarBotoes(false)
                pendente = "disconnect"
                pedidoAtual = mqtt?.enviar("DRIVE_DISCONNECT") ?: ""
            }
            .setNegativeButton(R.string.storage_cancelar, null)
            .show()
    }

    private fun abrirNavegador(url: String) {
        try {
            startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
        } catch (_: Exception) {
            fecharServidorLocal()
            txtStatus.text = getString(R.string.drive_na_internet)
            txtAviso.text = ""
            habilitarBotoes(true)
        }
    }

    private fun habilitarBotoes(ligado: Boolean) {
        btnConectar.isEnabled = ligado
        btnTestar.isEnabled = ligado
        btnDesconectar.isEnabled = ligado
    }

    private fun pegar(json: String): JSONObject? = try {
        JSONObject(json)
    } catch (_: Exception) {
        null
    }

    private fun paginaDeSucesso(): String = """
        <!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
        <meta name="viewport" content="width=device-width,initial-scale=1">
        <title>Conta conectada</title>
        <style>body{font-family:sans-serif;background:#f7f7f7;margin:0;padding:24px;
        color:#212121}div{background:#fff;padding:20px;border-radius:6px}
        h1{font-size:18px;margin:0 0 8px}p{font-size:14px;color:#616161;margin:0}</style>
        </head><body><div><h1>Conta conectada</h1>
        <p>Volte para o aplicativo Pregacao Controle. Voce ja pode fechar esta aba.</p>
        </div></body></html>
    """.trimIndent()

    private fun paginaDeErro(): String = """
        <!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
        <meta name="viewport" content="width=device-width,initial-scale=1">
        <title>Retorno inesperado</title>
        <style>body{font-family:sans-serif;background:#f7f7f7;margin:0;padding:24px;
        color:#212121}div{background:#fff;padding:20px;border-radius:6px}
        h1{font-size:18px;margin:0 0 8px}p{font-size:14px;color:#616161;margin:0}</style>
        </head><body><div><h1>Retorno inesperado</h1>
        <p>Volte para o aplicativo e tente conectar de novo.</p>
        </div></body></html>
    """.trimIndent()

    private companion object {
        const val LOCALHOST = "127.0.0.1"
        const val PORTA_PADRAO = 8080
    }
}
