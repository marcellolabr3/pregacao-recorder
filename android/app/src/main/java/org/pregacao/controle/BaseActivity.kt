package org.pregacao.controle

import android.app.Activity
import android.os.Build
import android.os.Bundle
import android.view.WindowInsets

/**
 * Activity que mantem o conteudo FORA das barras do sistema.
 *
 * Por que isto existe
 * -------------------
 * O APK mira `targetSdk 35`. A partir do Android 15 o sistema IMPOe
 * edge-to-edge: a janela passa a se desenhar por tras da barra de status e
 * da barra de navegacao, comecando em y=0 - e o conteudo que ali comecava
 * fica atras delas. E' o bug relatado: cabecalho cortado e itens escondidos
 * em TODAS as telas.
 *
 * As DUAS metades da correcao
 * ---------------------------
 * (1) PADDING no decorView. E' a unica vista que recebe os insets do sistema
 *     e tambem o pai da action bar, entao encaixar as barras aqui resolve a
 *     barra de status de uma vez: a action bar sai de tras dela. Sem AndroidX
 *     nao ha WindowInsetsCompat por aqui - o Framework entrega o que precisa.
 *
 * (2) CONSUMIR os insets depois (`WindowInsets.CONSUMED`). Devolve-los sem
 *     consumir (como na primeira tentativa) deixava o `ActionBarOverlayLayout`
 *     processar o inset do status bar em cima de um decorView que JA' estava
 *     paddingado: ele passava a montar a action bar POR CIMA do conteudo, e
 *     o resultado era exatamente uma action bar de altura de conteudo
 *     escondida em cada tela. Consumindo, os filhos voltam ao layout
 *     classico - action bar no topo, conteudo ABAIXO dela - porque o encaixe
 *     das barras ja' foi feito pelo padding e nao precisa mais ser repassado.
 *
 * O guardia por versao importa
 * ----------------------------
 * Abaixo do Android 15 nao ha edge-to-edge imposto: o sistema ja' encaixa a
 * janela sozinho. Registrar o listener em qualquer versao SUBSTITUI esse
 * encaixe padrao (o listener roda no lugar de `onApplyWindowInsets`), entao
 * em versoes antigas o resultado seria um padding a mais. So' a partir do
 * Android 15 o caminho antigo fica intacto e o padding entra no lugar do
 * encaixe que deixou de existir.
 */
open class BaseActivity : Activity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        encaixarBarrasDoSistema()
    }

    private fun encaixarBarrasDoSistema() {
        if (Build.VERSION.SDK_INT < 35) return

        // registrado ANTES do setContentView: o dispatch de insets so acontece
        // depois que a arvore e' anexada a janela, entao este listener ja' esta
        // no lugar quando a primeira leitura chega.
        window.decorView.setOnApplyWindowInsetsListener { vista, insets ->
            val barras = insets.getInsets(WindowInsets.Type.systemBars())
            vista.setPadding(barras.left, barras.top, barras.right, barras.bottom)
            // CONSUMIDO, nao devolvido: o encaixe ja' foi feito acima. Repassar
            // os insets faria o ActionBarOverlayLayout encaixa-los de novo e
            // colocar a action bar por cima do conteudo.
            WindowInsets.CONSUMED
        }
    }
}
