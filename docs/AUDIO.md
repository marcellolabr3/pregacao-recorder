# Audio no Windows

A captura usa FFmpeg/DirectShow. Instalar FFmpeg no PATH e verificar a interface
no gravador de som do Windows antes de abrir o sistema.

```powershell
ffmpeg -hide_banner -list_devices true -f dshow -i dummy
```

Em CONFIGURACOES AVANCADAS > AUDIO, escolher AUTO (preferencia USB) ou o nome
exato da interface. Ajustar taxa/canais compativeis com o equipamento.
Os segmentos preservam o audio para recuperacao; a consolidacao entrega um arquivo unico.

TESTAR SINAL e `scripts\pregacao.cmd check` capturam audio por 2 segundos.
SILENCIO significa sinal baixo: verificar fader, dispositivo, permissao de microfone
do Windows e canal USB da mesa. Sem interface ou FFmpeg, iniciar deve ser recusado.
Validacao de software nao substitui ouvir uma gravacao feita na mesa real.
