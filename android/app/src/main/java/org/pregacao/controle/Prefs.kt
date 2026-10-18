package org.pregacao.controle

import android.content.Context
import android.content.SharedPreferences

/**
 * Configuracao do operador, gravada uma unica vez no celular.
 *
 * Nada disto e segredo do equipamento: host, porta e ID sao publicos (estao
 * no painel). O token e a credencial do operador no servico remoto - ele fica
 * no aparelho do operador, nunca no codigo do APK.
 */
class Prefs(context: Context) {

    private val sp: SharedPreferences =
        context.getSharedPreferences("pregacao", Context.MODE_PRIVATE)

    /**
     * Host e ID do aparelho NAO sao segredos (estao no painel, em texto
     * puro) e nao mudam: vem de fabrica para o equipamento funcionar sem
     * depender de nada escondido na tela. Continuam editaveis em
     * Configuracoes. O TOKEN e que e credencial - ele continua sendo digitado.
     */
    var servidor: String
        get() = sp.getString("servidor", PADRAO_SERVIDOR) ?: PADRAO_SERVIDOR
        set(v) = sp.edit().putString("servidor", v.trim()).apply()

    var porta: Int
        get() = sp.getInt("porta", 8883)
        set(v) = sp.edit().putInt("porta", v).apply()

    var tls: Boolean
        get() = sp.getBoolean("tls", true)
        set(v) = sp.edit().putBoolean("tls", v).apply()

    var aparelho: String
        get() = sp.getString("aparelho", PADRAO_APARELHO) ?: PADRAO_APARELHO
        set(v) = sp.edit().putString("aparelho", v.trim()).apply()

    var usuario: String
        get() = sp.getString("usuario", "operador") ?: "operador"
        set(v) = sp.edit().putString("usuario", v.trim()).apply()

    var token: String
        get() = sp.getString("token", "") ?: ""
        set(v) = sp.edit().putString("token", v).apply()

    /**
     * Existe configuracao suficiente para tentar conectar?
     *
     * O token tambem entra aqui: host e ID vem de fabrica, entao sem o token
     * ainda nao ha o que conectar - e nesse caso a tela principal avisa para
     * abrir Configuracoes, em vez de tentar com credencial vazia e cair em
     * erro de autenticacao que nao explica nada ao operador.
     */
    fun pronto(): Boolean =
        servidor.isNotBlank() && aparelho.isNotBlank() && token.isNotBlank()

    companion object {
        const val PADRAO_SERVIDOR = "d1901dc1.ala.us-east-1.emqxsl.com"
        const val PADRAO_APARELHO = "pregacao-igreja-01"
    }
}
