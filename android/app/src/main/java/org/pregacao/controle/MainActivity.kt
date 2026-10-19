package org.pregacao.controle

import android.app.AlertDialog
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.Menu
import android.view.MenuItem
import android.widget.Button
import android.widget.ProgressBar
import android.widget.TextView
import org.json.JSONObject

/**
 * Tela unica de controle.
 *
 * Ela apenas EXIBE o estado que chega por MQTT e envia dois comandos
 * (START/STOP). Nada de audio e gravado aqui: o celular observa o
 * equipamento, nao substitui ele.
 *
 * Estende `BaseActivity` para que o conteudo nao fique atras das barras do
 * sistema no Android 15 (edge-to-edge imposto pelo targetSdk 35).
 */
class MainActivity : BaseActivity(), MqttController.Callbacks {

    private lateinit var prefs: Prefs
    private var mqtt: MqttController? = null

    private lateinit var txtDispositivo: TextView
    private lateinit var badge: TextView
    private lateinit var txtEstado: TextView
    private lateinit var txtDetalhe: TextView
    private lateinit var txtTempo: TextView
    private lateinit var btnAcao: Button
    private lateinit var txtMensagem: TextView
    private lateinit var txtUpload: TextView
    private lateinit var barraUpload: ProgressBar
    private lateinit var txtArquivo: TextView
    private lateinit var txtEventos: TextView
    private lateinit var txtAvisoArmazenamento: TextView

    private val handler = Handler(Looper.getMainLooper())
    private val eventos = ArrayDeque<String>()

    // estado vindo do equipamento
    private var online = false
    private var conectado = false
    private var estado = ""
    private var banner = ""
    private var detail = ""
    private var startedAt = 0.0
    private val arquivo = StringBuilder()

    // --------------------------------------------------------------
    // ciclo de vida
    // --------------------------------------------------------------
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        prefs = Prefs(this)

        txtDispositivo = findViewById(R.id.txtDispositivo)
        badge = findViewById(R.id.badgeConexao)
        txtEstado = findViewById(R.id.txtEstado)
        txtDetalhe = findViewById(R.id.txtDetalhe)
        txtTempo = findViewById(R.id.txtTempo)
        btnAcao = findViewById(R.id.btnAcao)
        txtMensagem = findViewById(R.id.txtMensagem)
        txtUpload = findViewById(R.id.txtUpload)
        barraUpload = findViewById(R.id.barraUpload)
        txtArquivo = findViewById(R.id.txtArquivo)
        txtEventos = findViewById(R.id.txtEventos)
        txtAvisoArmazenamento = findViewById(R.id.txtAvisoArmazenamento)

        // o aviso de destino caido e' o proprio atalho para a tela que
        // resolve o problema: tocar nele leva o operador para a escolha
        txtAvisoArmazenamento.setOnClickListener {
            startActivity(android.content.Intent(this, StorageActivity::class.java))
        }

        btnAcao.setOnClickListener { aoApertarAcao() }

        // qual build esta instalada, sempre visivel: sem isto o operador so
        // descobre a versao abrindo os Ajustes do Android.
        actionBar?.subtitle = "v" + BuildConfig.VERSION_NAME

        handler.post(ticker)
    }

    override fun onResume() {
        super.onResume()
        // roda ao voltar das configuracoes e ao reacender a tela: garante
        // que o nome e a conexao reflitam o que esta salvo agora
        if (prefs.pronto()) {
            txtDispositivo.text = prefs.aparelho
            if (mqtt == null) conectar()
        } else {
            txtMensagem.setText(R.string.sem_config)
        }
    }

    override fun onStop() {
        super.onStop()
        // a tela nao precisa manter a conexao em segundo plano; ao voltar,
        // onResume reconecta (com as configuracoes que existirem entao)
        mqtt?.desconectar()
        mqtt = null
    }

    override fun onDestroy() {
        handler.removeCallbacksAndMessages(null)
        super.onDestroy()
    }

    override fun onCreateOptionsMenu(menu: Menu): Boolean {
        menuInflater.inflate(R.menu.main, menu)
        return true
    }

    override fun onOptionsItemSelected(item: MenuItem): Boolean {
        if (item.itemId == R.id.acao_config) {
            startActivity(android.content.Intent(this, SettingsActivity::class.java))
            return true
        }
        if (item.itemId == R.id.acao_storage) {
            startActivity(android.content.Intent(this, StorageActivity::class.java))
            return true
        }
        if (item.itemId == R.id.acao_drive) {
            startActivity(android.content.Intent(this, DriveActivity::class.java))
            return true
        }
        return super.onOptionsItemSelected(item)
    }

    // --------------------------------------------------------------
    // conexao
    // --------------------------------------------------------------
    private fun conectar() {
        mqtt?.desconectar()
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
            conectado = ok
            if (!ok) online = false
            atualizarConexao()
            if (!ok) mostrarMensagem(detalhe)
        }
    }

    override fun disponibilidade(online: Boolean) {
        runOnUiThread {
            this.online = online
            atualizarConexao()
        }
    }

    override fun estado(retido: Boolean, json: String) {
        runOnUiThread { aplicarEstado(json) }
    }

    override fun ack(json: String) {
        runOnUiThread {
            val obj = pegar(json) ?: return@runOnUiThread
            val ok = obj.optBoolean("ok", false)
            val erro = obj.optString("error", "")
            val detalhe = obj.optString("detail", "")
            when {
                ok && detalhe.isNotBlank() -> mostrarMensagem(detalhe)
                ok -> mostrarMensagem("")
                erro.isNotBlank() -> mostrarMensagem(erro)
                else -> mostrarMensagem("resposta sem detalhe")
            }
        }
    }

    override fun evento(json: String) {
        runOnUiThread {
            val obj = pegar(json) ?: return@runOnUiThread
            val kind = obj.optString("kind", "")
            val data = obj.optJSONObject("data")
            val mensagem = data?.optString("message") ?: ""

            if (kind == "gravacao_pronta") {
                val caminho = data?.optString("path") ?: ""
                if (caminho.isNotBlank()) {
                    arquivo.clear()
                    arquivo.append(caminho.substringAfterLast('/').substringAfterLast('\\'))
                    txtArquivo.text = arquivo.toString()
                }
            }

            val hora = java.text.SimpleDateFormat("HH:mm", java.util.Locale.US)
                .format(java.util.Date())
            eventos.addFirst("$hora  ${kind.ifBlank { "evento" }}  $mensagem".trim())
            while (eventos.size > 6) eventos.removeLast()
            txtEventos.text = eventos.joinToString("\n")
        }
    }

    override fun comandoEnviado(ok: Boolean, detalhe: String) {
        runOnUiThread {
            if (!ok) mostrarMensagem(detalhe)
            btnAcao.isEnabled = false
            // o ack e quem libera o botao de novo (evita duplo toque)
            // cinto de seguranca: se o ack se perder, o botao nao fica morto
            handler.postDelayed({ atualizarBotao() }, 5000)
        }
    }

    // --------------------------------------------------------------
    // render
    // --------------------------------------------------------------
    private fun atualizarConexao() {
        val ligado = conectado && online
        badge.setText(if (ligado) R.string.estado_online else R.string.estado_offline)
        badge.setBackgroundColor(
            resources.getColor(if (ligado) R.color.online else R.color.offline, theme)
        )
        atualizarBotao()
        if (ligado) txtMensagem.text = ""
    }

    /**
     * O rotulo do botao diz a acao certa para o estado ATUAL: "INICIAR GRAVACAO"
     * quando parado, "ENCERRAR GRAVACAO" quando gravando e "AGUARDE..." enquanto o
     * equipamento trabalha (FINALIZANDO, ENVIANDO). Sem este metodo o operador veria
     * "INICIAR GRAVACAO" com a gravacao ja rolando - o botao usava o texto fixo do XML.
     *
     * INICIAR fica disponivel em IDLE, COMPLETED e ERROR: e' exatamente o que o
     * servidor aceita (recording.manager.start) e o que o painel web habilita
     * (web/static/app.js). Sem ERROR/COMPLETED aqui o botao travava em
     * "AGUARDE..." depois de um start recusado por falta de interface de audio
     * - e continuava travado depois que o operador plugava a interface.
     */
    private fun atualizarBotao() {
        val ligado = conectado && online
        when {
            !ligado -> {
                // sem enlace nao ha acao possivel; o rotulo indica a proxima acao
                btnAcao.setText(R.string.btn_iniciar)
                btnAcao.isEnabled = false
            }
            estado == "IDLE" || estado == "COMPLETED" || estado == "ERROR" -> {
                btnAcao.setText(R.string.btn_iniciar)
                btnAcao.isEnabled = true
            }
            estado == "RECORDING" -> {
                btnAcao.setText(R.string.btn_encerrar)
                btnAcao.isEnabled = true
            }
            estado.isEmpty() -> {
                // ainda nao recebemos estado do equipamento
                btnAcao.setText(R.string.btn_iniciar)
                btnAcao.isEnabled = false
            }
            else -> {
                // FINALIZING / UPLOADING / RECOVERY_REQUIRED: nada a mandar agora
                btnAcao.setText(R.string.btn_aguarde)
                btnAcao.isEnabled = false
            }
        }
    }

    private fun aplicarEstado(json: String) {
        val obj = pegar(json) ?: return
        estado = obj.optString("state", "")
        banner = obj.optString("banner", "")
        detail = obj.optString("detail", "")
        startedAt = obj.optDouble("started_at", 0.0)

        // o equipamento publica o aviso de destino junto com o estado: e' ele
        // que revela que as gravacoes estao caindo no disco do PC (SSD solto)
        mostrarAvisoArmazenamento(obj.optString("storage_aviso", ""))

        if (arquivo.isEmpty()) {
            txtArquivo.setText(R.string.arquivo_nenhum)
        }

        txtEstado.text = rotuloDe(estado, banner)
        txtEstado.setTextColor(resources.getColor(corDe(estado, banner), theme))
        txtDetalhe.text = detail

        atualizarUpload(obj.optJSONObject("uploads"))
        atualizarConexao()
        atualizarTempo()
    }

    private fun mostrarAvisoArmazenamento(texto: String) {
        if (texto.isBlank()) {
            txtAvisoArmazenamento.visibility = android.view.View.GONE
        } else {
            txtAvisoArmazenamento.text = texto
            txtAvisoArmazenamento.visibility = android.view.View.VISIBLE
        }
    }

    private fun rotuloDe(state: String, banner: String): String = when (state) {
        "IDLE" -> "PRONTO"
        "RECORDING" -> "GRAVANDO"
        "FINALIZING" -> "ENCERRANDO"
        "UPLOADING" -> "ENVIANDO AO DRIVE"
        "COMPLETED" -> "ENVIADO"
        "RECOVERY_REQUIRED" -> "ATENCAO - GRAVACAO INTERROMPIDA"
        "ERROR" -> banner.ifBlank { "ATENCAO" }
        else -> banner.ifBlank { state.ifBlank { "AGUARDANDO" } }
    }

    private fun corDe(state: String, banner: String): Int = when (state) {
        "RECORDING" -> R.color.gravando
        "IDLE" -> R.color.pronto
        "ERROR", "RECOVERY_REQUIRED" -> R.color.atencao
        "UPLOADING" -> R.color.enviando
        "COMPLETED" -> R.color.enviado
        else -> if (banner.isNotBlank()) R.color.atencao else R.color.texto_fraco
    }

    private fun atualizarUpload(uploads: JSONObject?) {
        val pendentes = uploads?.optInt("pending", 0) ?: 0
        val rodando = uploads?.optInt("running", 0) ?: 0
        val falhos = uploads?.optInt("failed", 0) ?: 0
        val feitos = uploads?.optInt("done", 0) ?: 0

        val texto: String
        val cor: Int
        val mostrandoBarra: Boolean
        when {
            rodando > 0 -> {
                texto = "ENVIANDO"
                cor = R.color.enviando
                mostrandoBarra = true
            }
            pendentes > 0 -> {
                texto = "PENDENTE ($pendentes)"
                cor = R.color.atencao
                mostrandoBarra = false
            }
            falhos > 0 -> {
                texto = "FALHOU ($falhos)"
                cor = R.color.gravando
                mostrandoBarra = false
            }
            feitos > 0 -> {
                texto = "ENVIADO"
                cor = R.color.enviado
                mostrandoBarra = false
            }
            else -> {
                texto = getString(R.string.upload_off)
                cor = R.color.texto_fraco
                mostrandoBarra = false
            }
        }
        txtUpload.text = texto
        txtUpload.setTextColor(resources.getColor(cor, theme))
        barraUpload.visibility =
            if (mostrandoBarra) android.view.View.VISIBLE else android.view.View.GONE
    }

    private fun atualizarTempo() {
        if (estado == "RECORDING" && startedAt > 0) {
            val segundos = (System.currentTimeMillis() / 1000.0 - startedAt).toLong()
            txtTempo.text = formatarTempo(segundos.coerceAtLeast(0))
        } else if (estado != "RECORDING") {
            txtTempo.setText(R.string.tempo_zero)
        }
    }

    private val ticker = object : Runnable {
        override fun run() {
            atualizarTempo()
            handler.postDelayed(this, 1000)
        }
    }

    // --------------------------------------------------------------
    // acoes
    // --------------------------------------------------------------
    private fun aoApertarAcao() {
        when (estado) {
            "IDLE" -> {
                btnAcao.isEnabled = false
                mqtt?.enviar("START")
            }
            "RECORDING" -> {
                AlertDialog.Builder(this)
                    .setTitle("Encerrar gravacao?")
                    .setMessage("A gravacao sera finalizada e o arquivo comecara a ser salvo.")
                    .setPositiveButton("ENCERRAR") { _, _ ->
                        btnAcao.isEnabled = false
                        mqtt?.enviar("STOP")
                    }
                    .setNegativeButton("CANCELAR", null)
                    .show()
            }
        }
    }

    private fun mostrarMensagem(texto: String) {
        txtMensagem.text = texto
        // volta a habilitar o botao quando o equipamento reagir
        handler.postDelayed({ atualizarBotao() }, 800)
        if (texto.isBlank()) return
    }

    private fun pegar(json: String): JSONObject? = try {
        JSONObject(json)
    } catch (_: Exception) {
        null
    }

    private fun formatarTempo(total: Long): String {
        val h = total / 3600
        val m = (total % 3600) / 60
        val s = total % 60
        return String.format(java.util.Locale.US, "%02d:%02d:%02d", h, m, s)
    }
}
