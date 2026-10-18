package org.pregacao.controle

import android.app.AlertDialog
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.text.InputType
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ListView
import android.widget.TextView
import org.json.JSONObject

/**
 * Redes Wi-Fi do EQUIPAMENTO.
 *
 * O celular nao mexe no proprio Wi-Fi: ele pede a lista, o equipamento varre
 * com o nmcli e devolve no ack; ao escolher uma rede a senha viaja no
 * comando WIFI_CONNECT e quem conecta e o Raspberry. Por isso a tela avisa
 * de cara que aquelas sao as redes que o EQUIPAMENTO enxerga - sem isso o
 * operador acha que esta conectando o celular em alguma rede.
 *
 * Cada tela tem a propria conexao MQTT (a MainActivity desconecta no onStop
 * ao abrir aqui), entao o ack que chega e resposta deste pedido e nao dos
 * comandos de gravacao. Mesmo assim o req_id e conferido: e ele que diz a
 * qual pedido a resposta pertence.
 *
 * Estende `BaseActivity` para que a lista nao comece atras da barra de
 * status no Android 15.
 */
class WifiActivity : BaseActivity(), MqttController.Callbacks {

    private lateinit var prefs: Prefs
    private var mqtt: MqttController? = null

    private lateinit var txtStatus: TextView
    private lateinit var lista: ListView
    private lateinit var btnProcurar: Button

    private val handler = Handler(Looper.getMainLooper())
    private var redes: List<JSONObject> = emptyList()

    /** req_id do pedido em andamento - so acks com este valor sao aceitos. */
    private var pedidoAtual = ""

    /** true enquanto o que esta pendente e um WIFI_CONNECT (e nao um SCAN). */
    private var conectando = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_wifi)
        prefs = Prefs(this)

        txtStatus = findViewById(R.id.txtWifiStatus)
        lista = findViewById(R.id.listaRedes)
        btnProcurar = findViewById(R.id.btnProcurar)

        btnProcurar.setOnClickListener { pedirRedes() }
        lista.setOnItemClickListener { _, _, posicao, _ ->
            val rede = redes.getOrNull(posicao)
            if (rede != null) escolherRede(rede)
        }

        // a versao instalada, sempre visivel (mesmo criterio da tela principal)
        actionBar?.subtitle = "v" + BuildConfig.VERSION_NAME
    }

    override fun onResume() {
        super.onResume()
        if (mqtt == null) iniciar()
    }

    override fun onStop() {
        super.onStop()
        // a conexao nao precisa ficar viva em segundo plano; ao voltar,
        // onResume reconecta e o equipamento entrega a lista de novo
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
            txtStatus.setText(R.string.wifi_sem_config)
            btnProcurar.isEnabled = false
            return
        }
        txtStatus.setText(R.string.wifi_procurando)
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
                pedirRedes()
            } else {
                txtStatus.text = detalhe
                btnProcurar.isEnabled = true
            }
        }
    }

    override fun disponibilidade(online: Boolean) {
        // esta tela so interessa o ack: o "online" ja aparece na tela principal
    }

    override fun estado(retido: Boolean, json: String) {
        // idem - o estado da gravacao nao muda a lista de redes
    }

    override fun evento(json: String) {
        // notificacoes vao para a tela principal
    }

    override fun comandoEnviado(ok: Boolean, detalhe: String) {
        runOnUiThread {
            if (ok) return@runOnUiThread
            // publicacao recusada: mostra por que e libera o botao. Nao se
            // mexe em "conectando"/"pedidoAtual" aqui - quem os rearmazena e
            // o proximo pedido, e esse callback chega antes do ack.
            txtStatus.text = detalhe
            btnProcurar.isEnabled = true
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

        val ok = obj.optBoolean("ok", false)
        val erro = obj.optString("error", "")

        if (conectando) {
            conectando = false
            btnProcurar.isEnabled = true
            if (ok) {
                val ssid = obj.optString("ssid", "")
                txtStatus.text = getString(R.string.wifi_conectado, ssid)
                // recarrega em seguida: a lista ja deve refletir a conexao
                handler.postDelayed({ pedirRedes() }, 4000)
            } else {
                txtStatus.text = erro.ifBlank { "falha ao conectar na rede" }
            }
            return
        }

        if (!ok) {
            txtStatus.text = erro.ifBlank { "falha ao procurar as redes" }
            btnProcurar.isEnabled = true
            return
        }

        val array = obj.optJSONArray("networks")
        redes = if (array == null) {
            emptyList()
        } else {
            (0 until array.length()).mapNotNull { array.optJSONObject(it) }
        }
        renderizar()
    }

    private fun renderizar() {
        btnProcurar.isEnabled = true
        if (redes.isEmpty()) {
            txtStatus.setText(R.string.wifi_nenhuma)
            lista.adapter = null
            return
        }
        txtStatus.text = getString(R.string.wifi_achadas, redes.size)
        lista.adapter = ArrayAdapter(
            this,
            android.R.layout.simple_list_item_1,
            redes.map { formatar(it) },
        )
    }

    private fun formatar(rede: JSONObject): String {
        val ssid = rede.optString("ssid", "").ifBlank { "(rede oculta)" }
        // o equipamento devolve tanto "strength" (Forte/Fraco) quanto
        // "signal" (0-100): usa o que houver, sem depender de um deles
        val forca = rede.optString("strength", "")
            .ifBlank { rede.optInt("signal", 0).toString() + "%" }
        val seguranca = rede.optString("security", "")
            .ifBlank {
                if (rede.optBoolean("secure", false)) "protegida" else "aberta"
            }
        return "$ssid\n$forca  -  $seguranca"
    }

    // --------------------------------------------------------------
    // acoes
    // --------------------------------------------------------------
    private fun pedirRedes() {
        conectando = false
        btnProcurar.isEnabled = false
        txtStatus.setText(R.string.wifi_procurando)
        pedidoAtual = mqtt?.enviar("WIFI_SCAN") ?: ""
    }

    private fun escolherRede(rede: JSONObject) {
        val ssid = rede.optString("ssid", "").trim()
        if (ssid.isBlank()) return

        if (!rede.optBoolean("secure", true)) {
            conectar(ssid, null)
            return
        }

        val campo = EditText(this).apply {
            inputType =
                InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
            hint = getString(R.string.wifi_senha)
        }
        val margem = (20 * resources.displayMetrics.density).toInt()
        val envoltorio = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(margem, margem / 2, margem, 0)
            addView(campo)
        }

        AlertDialog.Builder(this)
            .setTitle(ssid)
            .setMessage(R.string.wifi_senha_msg)
            .setView(envoltorio)
            .setPositiveButton(R.string.wifi_conectar) { _, _ ->
                conectar(ssid, campo.text.toString())
            }
            .setNegativeButton(R.string.wifi_cancelar, null)
            .show()
    }

    private fun conectar(ssid: String, senha: String?) {
        btnProcurar.isEnabled = false
        txtStatus.text = getString(R.string.wifi_conectando, ssid)
        val extras = mutableMapOf("ssid" to ssid)
        if (!senha.isNullOrBlank()) extras["password"] = senha
        conectando = true
        pedidoAtual = mqtt?.enviar("WIFI_CONNECT", extras) ?: ""
    }

    private fun pegar(json: String): JSONObject? = try {
        JSONObject(json)
    } catch (_: Exception) {
        null
    }
}
