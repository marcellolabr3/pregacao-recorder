package org.pregacao.controle

import android.app.AlertDialog
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.ListView
import android.widget.TextView
import android.widget.Toast
import org.json.JSONObject
import java.util.Locale

/**
 * Onde o equipamento grava: SSD externo ou disco do PC.
 *
 * Este e' o front do problema relatado - o SSD desconecta e as gravacoes
 * passam a cair no disco do PC sem que ninguem perceba. Aqui o operador ve os
 * destinos que o PC ENXERGA de verdade (o painel enumera os discos do Windows) e
 * troca o destino; o equipamento recusa um disco que nao esta montado, para
 * que a troca nunca seja ilusoria.
 *
 * Segue o mesmo desenho da tela de Wi-Fi: cada tela tem a propria conexao
 * MQTT e o ack e filtrado por req_id, entao a resposta que chega e deste
 * pedido e nao dos comandos de gravacao da tela principal.
 */
class StorageActivity : BaseActivity(), MqttController.Callbacks {

    private lateinit var prefs: Prefs
    private var mqtt: MqttController? = null

    private lateinit var txtStatus: TextView
    private lateinit var txtAviso: TextView
    private lateinit var lista: ListView
    private lateinit var btnAtualizar: Button

    private val handler = Handler(Looper.getMainLooper())
    private var destinos: List<JSONObject> = emptyList()
    private var atual = ""

    /** req_id do pedido em andamento - so acks com este valor sao aceitos. */
    private var pedidoAtual = ""

    /** true enquanto o que esta pendente e um STORAGE_SET (e nao um LIST). */
    private var trocando = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_storage)
        prefs = Prefs(this)

        txtStatus = findViewById(R.id.txtStorageStatus)
        txtAviso = findViewById(R.id.txtStorageAviso)
        lista = findViewById(R.id.listaDestinos)
        btnAtualizar = findViewById(R.id.btnAtualizar)

        btnAtualizar.setOnClickListener { pedirDestinos() }
        lista.setOnItemClickListener { _, _, posicao, _ ->
            destinos.getOrNull(posicao)?.let { escolherDestino(it) }
        }

        actionBar?.subtitle = "v" + BuildConfig.VERSION_NAME
    }

    override fun onResume() {
        super.onResume()
        if (mqtt == null) iniciar()
    }

    override fun onStop() {
        super.onStop()
        mqtt?.desconectar()
        mqtt = null
    }

    override fun onDestroy() {
        handler.removeCallbacksAndMessages(null)
        super.onDestroy()
    }

    // --------------------------------------------------------------
    // conexao
    // --------------------------------------------------------------
    private fun iniciar() {
        if (!prefs.pronto()) {
            txtStatus.setText(R.string.storage_sem_config)
            btnAtualizar.isEnabled = false
            return
        }
        txtStatus.setText(R.string.storage_carregando)
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
                pedirDestinos()
            } else {
                txtStatus.text = detalhe
                btnAtualizar.isEnabled = true
            }
        }
    }

    override fun disponibilidade(online: Boolean) = Unit

    override fun estado(retido: Boolean, json: String) = Unit

    override fun evento(json: String) = Unit

    override fun comandoEnviado(ok: Boolean, detalhe: String) {
        runOnUiThread {
            if (ok) return@runOnUiThread
            // publicacao recusada: mostra por que e libera o botao
            txtStatus.text = detalhe
            btnAtualizar.isEnabled = true
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

        if (trocando) {
            trocando = false
            btnAtualizar.isEnabled = true
            if (obj.optBoolean("ok", false)) {
                Toast.makeText(
                    this, R.string.storage_alterado, Toast.LENGTH_SHORT
                ).show()
                handler.postDelayed({ pedirDestinos() }, 500)
            } else {
                Toast.makeText(
                    this,
                    obj.optString("error", "falha ao trocar o destino"),
                    Toast.LENGTH_LONG,
                ).show()
            }
            return
        }

        if (!obj.optBoolean("ok", false)) {
            txtStatus.text = obj.optString("error", "falha ao ler os destinos")
            btnAtualizar.isEnabled = true
            return
        }

        val storage = obj.optJSONObject("storage")
        if (storage == null) {
            txtStatus.setText(R.string.storage_nenhuma)
            btnAtualizar.isEnabled = true
            return
        }

        atual = storage.optString("current", "")
        mostrarAviso(storage.optString("aviso", ""))

        val itens = storage.optJSONArray("items")
        destinos = if (itens == null) {
            emptyList()
        } else {
            (0 until itens.length()).mapNotNull { itens.optJSONObject(it) }
        }
        renderizar()
    }

    /**
     * O aviso e' o coracao desta tela: ele acende quando o destino escolhido
     * nao esta mais montado e as gravacoes estao caindo no disco do PC. Sem
     * ele o operador so descobre tarde.
     */
    private fun mostrarAviso(texto: String) {
        if (texto.isBlank()) {
            txtAviso.visibility = android.view.View.GONE
        } else {
            txtAviso.text = texto
            txtAviso.visibility = android.view.View.VISIBLE
        }
    }

    private fun renderizar() {
        btnAtualizar.isEnabled = true
        if (destinos.isEmpty()) {
            txtStatus.setText(R.string.storage_nenhuma)
            lista.adapter = null
            return
        }
        txtStatus.text = getString(
            R.string.storage_gravando_em, atual.ifBlank { "-" }
        )
        lista.adapter = ArrayAdapter(
            this,
            android.R.layout.simple_list_item_1,
            destinos.map { formatar(it) },
        )
    }

    /** Linha da lista: rotulo, caminho, marcadores e espaco livre. */
    private fun formatar(item: JSONObject): String {
        val caminho = item.optString("caminho", "")
        val rotulo = item.optString("rotulo", "").ifBlank { caminho }

        val marcadores = mutableListOf<String>()
        if (item.optBoolean("atual", false)) {
            marcadores.add(getString(R.string.storage_atual_rotulo))
        }
        val disponivel = item.optBoolean("montado", false) &&
            item.optBoolean("gravavel", false)
        if (!disponivel) marcadores.add(getString(R.string.storage_indisponivel))

        val disco = item.optJSONObject("disco")
        val espaco = if (disco != null && disco.optBoolean("ok", false)) {
            String.format(
                Locale.US,
                "%.0f GB livres",
                disco.optDouble("livre_gb", 0.0),
            )
        } else {
            getString(R.string.storage_sem_espaco)
        }

        val cabeca = if (marcadores.isEmpty()) rotulo
        else "$rotulo  [" + marcadores.joinToString(" - ") + "]"
        return "$cabeca\n$caminho\n$espaco"
    }

    // --------------------------------------------------------------
    // acoes
    // --------------------------------------------------------------
    private fun pedirDestinos() {
        trocando = false
        btnAtualizar.isEnabled = false
        txtStatus.setText(R.string.storage_carregando)
        pedidoAtual = mqtt?.enviar("STORAGE_LIST") ?: ""
    }

    private fun escolherDestino(item: JSONObject) {
        val caminho = item.optString("caminho", "").trim()
        if (caminho.isBlank() || caminho == atual) return

        AlertDialog.Builder(this)
            .setTitle(R.string.storage_confirmar)
            .setMessage(getString(R.string.storage_confirmar_msg, caminho))
            .setPositiveButton(R.string.storage_trocar) { _, _ ->
                trocarDestino(caminho)
            }
            .setNegativeButton(R.string.storage_cancelar, null)
            .show()
    }

    private fun trocarDestino(caminho: String) {
        btnAtualizar.isEnabled = false
        trocando = true
        pedidoAtual = mqtt?.enviar("STORAGE_SET", mapOf("path" to caminho)) ?: ""
    }

    private fun pegar(json: String): JSONObject? = try {
        JSONObject(json)
    } catch (_: Exception) {
        null
    }
}
