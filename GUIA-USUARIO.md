# GUIA DO USUARIO

Este guia e para quem **usa** o equipamento. Nao precisa saber de
tecnologia: sao apenas 9 assuntos.

---

## 1. Como acessar pelo celular

1. Ligue o equipamento (ele ja inicia sozinho).
2. Com o celular conectado no **mesmo Wi-Fi da igreja**,
3. abra o navegador (Chrome, Safari...) e digite:

   ```
   http://pregacao-pi.local:8080
   ```

   Se nao abrir, use o numero do equipamento (pega com quem instalou):

   ```
   http://192.168.0.10:8080
   ```

4. Digite o **PIN** quando pedir.

> Dica: salve nos favoritos do celular para abrir com um toque.

---

## 2. Como iniciar uma gravacao

1. Na tela principal, confira se aparece **PRONTO** (verde).
2. Toque em **INICIAR GRAVACAO**.
3. A tela passa a mostrar **GRAVANDO** e o cronometro comeca a contar.
4. Pode travar o celular ou trocar de aba - a gravacao continua sozinha.

---

## 3. Como finalizar uma gravacao

1. Toque em **FINALIZAR GRAVACAO**.
2. Vai aparecer: **"Tem certeza que deseja finalizar a gravacao?"**
3. Toque em **FINALIZAR** (ou CANCELAR, se foi engano).
4. A tela mostra **FINALIZANDO** e depois **PRONTO** de novo.
5. Aguarde a mensagem de concluido - nao desligue o equipamento nesse
   momento.

> Se voce finalizar **logo apos iniciar** (antes de o som chegar), o
> equipamento mostra **"Gravacao vazia descartada"** e volta para PRONTO.
> Nao e erro: simplesmente nao havia audio para salvar.

---

## 4. Como verificar se foi enviada

* No topo aparece o cartao **ULTIMA GRAVACAO** com o nome do arquivo.
* Toque em **HISTORICO** (menu de cima): cada gravacao mostra
  **ENVIADO** (verde) ou **PENDENTE** (amarelo), com o caminho no Google
  Drive.
* No Drive do celular/computador, abra a pasta **Pregacoes** - o arquivo
  deve estar la.

---

## 5. Se aparecer "GRAVACAO INTERROMPIDA"

Isso significa que a **luz acabou** ou o equipamento reiniciou no meio da
gravacao.

**O que voce precisa fazer:**

1. Não entre em pânico: **o audio gravado esta salvo**.
2. Na tela, no cartao **GRAVACAO INTERROMPIDA**, toque em **RECUPERAR**.
3. O equipamento conserta o arquivo e ele passa a aparecer no historico,
   normalmente com upload em seguida.
4. So toque em **DESCARTAR** se tiver certeza de que nao quer aquele audio
   (pede confirmacao antes).

> Lembrete: o equipamento **nao avisa enquanto esta desligado**. A aviso
> aparece assim que ele volta a funcionar.

---

## 6. Se aparecer "UPLOAD PENDENTE"

Significa que **a internet caiu** (ou o Drive esta desconectado) - o arquivo
ja esta **salvo no equipamento**.

**O que fazer:**

1. Nao grave por cima nem apague nada - nada vai se perder.
2. Confira se a internet voltou (cartao REDE mostra ONLINE).
3. Assim que a internet voltar, **o envio acontece sozinho**.
4. Se quiser forcar agora, toque em **REENVIAR FILA** (cartao GOOGLE DRIVE).
5. Confira em **HISTORICO** ate aparecer **ENVIADO**.

---

## 7. Se a rede da igreja cair

Enquanto gravando ou parado, se o equipamento ficar **sem Internet e sem
Wi-Fi**, ele monta a propria rede sozinho para voce nao ficar sem controle:

1. Espere de 12 a 45 segundos.
2. No Wi-Fi do celular vai aparecer uma rede chamada
   **PREGACAO-PI-XXXX** (os numeros vem do equipamento).
3. Conecte nela com a senha **pregacao12345**.
4. Abra no navegador:

   ```
   http://192.168.50.1:8080
   ```

5. Digite o PIN normalmente. Assim que a rede da igreja voltar, essa rede
   some sozinha e o equipamento volta ao IP normal.

> A gravacao nao para em nenhum momento - isso serve apenas para voce
> alcancar a interface.

### Como ligar (ou desligar) essa rede na mao

1. Vá em **CONFIG -> REDE** (vai pedir o PIN de administrador).
2. Toque em **ATIVAR MODO DE CONFIGURACAO** e confirme o aviso.
3. A rede `PREGACAO-PI-XXXX` passa a ser emitida. **DESATIVAR** desliga e
   devolve o Wi-Fi normal.

> Enquanto o modo de configuracao estiver ligado, o equipamento nao fica
> conectado no Wi-Fi da igreja. Para uso normal, deixe-o **DESATIVADO**.

---

## 8. Como trocar o Wi-Fi da igreja

1. **CONFIG -> REDE** (pede o PIN de administrador).
2. Toque em **PROCURAR REDES**.
3. Toque na rede desejada, digite a senha e **CONECTAR**.
4. Confira o IP aparecer em **WI-FI**.

> A senha digitada **nunca aparece** na tela nem em log. Se voce errar a
> senha, aparece um aviso e nada se perde - o equipamento continua
> acessivel.

---

## 9. Como acessar o equipamento de fora da igreja

Esse recurso usa o **Tailscale**, que cria um tunel privado entre a igreja e
os seus aparelhos - **sem abrir porta no roteador**.

1. **CONFIG -> REDE** (PIN de administrador) -> **AUTENTICAR**.
2. Abra o link de autenticacao e entre com a conta Tailscale da igreja
   (conta gratuita).
3. O painel passa a mostrar **ACESSO REMOTO = CONECTADO** e lista um endereco
   `http://100.x.x.x:8080` em **ACESSOS DO PAINEL** - copie esse endereco.
4. No celular, instale o aplicativo **Tailscale** e entre com a mesma conta.
5. Com o 4G ligado (fora do Wi-Fi da igreja), abra o endereco copiado: o
   painel carrega normalmente.

> O acesso tambem funciona pelo computador, com o Tailscale instalado.
> Se o equipamento reiniciar, o Tailscale volta sozinho - nao precisa
> autenticar de novo.

---

## 10. Como controlar pelo aplicativo (APK) de qualquer lugar

O aplicativo **nao precisa** do Tailscale nem de nada instalado na igreja:
ele conversa com o equipamento pela Internet, direto.

1. Instale o arquivo `.apk` no celular (quem instalou o equipamento envia).
2. Abra o aplicativo e, em **Configuracoes**, digite o **host**, o **ID do
   aparelho** e o **token do operador** uma unica vez. Host, ID e token
   aparecem no painel, no cartao **CONTROLE REMOTO** (somente com o PIN de
   administrador). O usuario ja vem preenchido (`operador`).
3. Pronto: a tela mostra **ONLINE** e o equipamento **PRONTO** ou
   **GRAVANDO**.

O que da para fazer:

| Botao | O que faz |
|---|---|
| **INICIAR** | comeca a gravar (igual ao painel) |
| **ENCERRAR** | finaliza a gravacao (pede confirmacao antes) |
| **AGUARDE...** | o equipamento esta encerrando ou enviando - nao aperte nada |
| **TEMPO** | mostra ha quanto tempo esta gravando |
| **Upload** | mostra ENVIANDO -> ENVIADO |
| **ARQUIVO** | mostra o nome do arquivo quando termina |

> **O aplicativo nao grava nem guarda som.** Ele so controla e acompanha;
> o audio continua sendo salvo no SSD do equipamento.

Se a Internet cair, o aplicativo mostra **OFFLINE** - mas a gravacao **nao
para**, e quando a conexao voltar o arquivo sobe sozinho ao Drive.

---

## Resumo visual

```
LIGAR
  |
ABRIR PELO CELULAR
  |
INICIAR
  |
GRAVANDO
  |
FINALIZAR
  |
CONFIRMAR
  |
UPLOAD
  |
CONCLUIDO
```

Em caso de duvida, procure quem instalou o equipamento (ou veja
`INSTALACAO-RASPBERRY.md`, para o administrador).
