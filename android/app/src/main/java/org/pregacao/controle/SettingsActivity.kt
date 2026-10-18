package org.pregacao.controle

import android.os.Bundle
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.ScrollView
import android.widget.Switch
import android.widget.Toast

/**
 * Onde o operador digita, uma unica vez, como falar com o equipamento.
 *
 * Host, porta e ID do aparelho vem do painel (cartao CONTROLE REMOTO).
 * O token e a credencial do operador - fica guardado so no celular.
 *
 * Estende `BaseActivity` para que os campos de baixo nao fiquem atras da
 * barra de navegacao no Android 15.
 */
class SettingsActivity : BaseActivity() {

    private lateinit var prefs: Prefs
    private lateinit var rolagem: ScrollView
    private lateinit var servidor: EditText
    private lateinit var porta: EditText
    private lateinit var tls: Switch
    private lateinit var aparelho: EditText
    private lateinit var usuario: EditText
    private lateinit var token: EditText

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_settings)
        prefs = Prefs(this)
        rolagem = findViewById(R.id.rolagem)

        servidor = findViewById(R.id.campoServidor)
        porta = findViewById(R.id.campoPorta)
        tls = findViewById(R.id.campoTls)
        aparelho = findViewById(R.id.campoAparelho)
        usuario = findViewById(R.id.campoUsuario)
        token = findViewById(R.id.campoToken)

        // Preenche com o que ja existe. Se a tela foi recriada (rotacao ou
        // teclado), o texto digitado estava no savedInstanceState e ele PREVALECE
        // - senao o que o operador digitou seria apagado por este setText.
        if (savedInstanceState != null) {
            servidor.setText(savedInstanceState.getString(CAMPO_SERVIDOR, ""))
            porta.setText(savedInstanceState.getString(CAMPO_PORTA, ""))
            aparelho.setText(savedInstanceState.getString(CAMPO_APARELHO, ""))
            usuario.setText(savedInstanceState.getString(CAMPO_USUARIO, ""))
            token.setText(savedInstanceState.getString(CAMPO_TOKEN, ""))
            tls.isChecked = savedInstanceState.getBoolean(CAMPO_TLS, prefs.tls)
        } else {
            servidor.setText(prefs.servidor)
            porta.setText(String.format(java.util.Locale.US, "%d", prefs.porta))
            tls.isChecked = prefs.tls
            aparelho.setText(prefs.aparelho)
            usuario.setText(prefs.usuario)
            token.setText(prefs.token)
        }

        findViewById<Button>(R.id.btnSalvar).setOnClickListener { salvar() }
    }

    // guarda o que esta sendo digitado para sobreviver a recriacao da tela
    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        outState.putString(CAMPO_SERVIDOR, servidor.text.toString())
        outState.putString(CAMPO_PORTA, porta.text.toString())
        outState.putBoolean(CAMPO_TLS, tls.isChecked)
        outState.putString(CAMPO_APARELHO, aparelho.text.toString())
        outState.putString(CAMPO_USUARIO, usuario.text.toString())
        outState.putString(CAMPO_TOKEN, token.text.toString())
    }

    private fun salvar() {
        val host = servidor.text.toString().trim()
        val id = aparelho.text.toString().trim()

        // diz QUAL campo falta - uma mensagem generica nao ajuda a diagnosticar
        val semServidor = host.isBlank()
        val semAparelho = id.isBlank()
        if (semServidor || semAparelho) {
            val aviso = when {
                semServidor && semAparelho -> R.string.cfg_vazio
                semServidor -> R.string.cfg_falta_servidor
                else -> R.string.cfg_falta_aparelho
            }
            Toast.makeText(this, aviso, Toast.LENGTH_LONG).show()
            // o campo pode estar acima do que a tela mostra (o teclado empurra a
            // lista para baixo): leva a vista ate ele e poe o cursor la
            rolarPara(if (semServidor) servidor else aparelho)
            return
        }

        val portaNum = porta.text.toString().toIntOrNull() ?: 8883

        prefs.servidor = host
        prefs.porta = portaNum
        prefs.tls = tls.isChecked
        prefs.aparelho = id
        prefs.usuario = usuario.text.toString().trim().ifBlank { "operador" }
        prefs.token = token.text.toString()

        Toast.makeText(this, R.string.cfg_salvo, Toast.LENGTH_SHORT).show()
        finish() // volta para a tela principal, que reconecta sozinha
    }

    /**
     * Leva a tela ate um campo e poe o cursor nele. Os campos ficam dentro de
     * um ScrollView dentro de um LinearLayout, entao a altura e somada dos
     * pais - `requestFocus` sozinho nem sempre rola ate la quando o teclado
     * ja tinha empurrado a lista para baixo.
     */
    private fun rolarPara(alvo: View) {
        alvo.requestFocus()
        alvo.post {
            var y = 0
            var atual: View? = alvo
            while (atual != null && atual !== rolagem) {
                y += atual.top
                atual = atual.parent as? View
            }
            rolagem.smoothScrollTo(0, (y - 24).coerceAtLeast(0))
        }
    }

    private companion object {
        const val CAMPO_SERVIDOR = "campo_servidor"
        const val CAMPO_PORTA = "campo_porta"
        const val CAMPO_TLS = "campo_tls"
        const val CAMPO_APARELHO = "campo_aparelho"
        const val CAMPO_USUARIO = "campo_usuario"
        const val CAMPO_TOKEN = "campo_token"
    }
}
