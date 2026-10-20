/* pregacao-recorder - interface web
   O NAVEGADOR NUNCA decide se o PC esta gravando.
   Ele apenas exibe o estado devolvido pelo servidor (fonte de verdade). */

(function () {
  "use strict";

  var status = null;
  var authed = false;
  var pinRequired = false;
  var isAdmin = false;
  var adminReturnView = "advanced";
  var wizStep = 1;              // assistente de primeiro acesso
  var clockOffset = 0;      // servidor - navegador
  var source = null;
  var notifCount = 0;
  var nlmUltimo = null;
  var nlmLoginPedido = false;
  var nlmDiagnostico = false;

  var $ = function (id) { return document.getElementById(id); };

  // ---------------------------------------------------------------- utils
  function api(path, method, body) {
    return fetch(path, {
      method: method || "GET",
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
      credentials: "same-origin"
    }).then(function (resp) {
      if (resp.status === 401) {
        authed = false;
        isAdmin = false;
        renderRemotePairing(null);
        showLogin(true);
        throw new Error("PIN obrigatorio");
      }
      return resp.json().catch(function () { return {}; }).then(function (data) {
        if (!resp.ok) {
          var err = new Error(data.message || ("erro " + resp.status));
          err.data = data;
          throw err;
        }
        return data;
      });
    });
  }

  function pad(n) { return (n < 10 ? "0" : "") + n; }

  function hms(total) {
    total = Math.max(0, Math.floor(total));
    var h = Math.floor(total / 3600);
    var m = Math.floor((total % 3600) / 60);
    var s = total % 60;
    return pad(h) + ":" + pad(m) + ":" + pad(s);
  }

  function bytes(v) {
    if (v === null || v === undefined) return "--";
    var u = ["B", "KB", "MB", "GB", "TB"], i = 0;
    v = Number(v);
    while (v >= 1024 && i < u.length - 1) { v /= 1024; i++; }
    return (i === 0 ? v : v.toFixed(1)) + " " + u[i];
  }

  function hora(ts) {
    if (!ts) return "--";
    var d = new Date(ts * 1000);
    return pad(d.getHours()) + ":" + pad(d.getMinutes()) + ":" + pad(d.getSeconds());
  }

  function dataHora(ts) {
    if (!ts) return "--";
    var d = new Date(ts * 1000);
    return pad(d.getDate()) + "/" + pad(d.getMonth() + 1) + "/" + d.getFullYear() +
           " " + pad(d.getHours()) + ":" + pad(d.getMinutes());
  }

  // ---------------------------------------------------------------- toasts
  function toast(message, level) {
    var box = $("toasts");
    var el = document.createElement("div");
    el.className = "toast " + (level || "info");
    el.textContent = message;
    box.appendChild(el);
    setTimeout(function () {
      el.style.transition = "opacity .4s";
      el.style.opacity = "0";
      setTimeout(function () { el.remove(); }, 400);
    }, 5200);
  }

  function addNotif(message, level, ts) {
    var list = $("notifications");
    var li = document.createElement("li");
    var lvl = document.createElement("span");
    lvl.className = "lvl " + (level || "info");
    var body = document.createElement("div");
    var txt = document.createElement("span");
    txt.textContent = message;
    var time = document.createElement("time");
    time.textContent = hora((ts || Date.now() / 1000));
    body.appendChild(txt);
    body.appendChild(time);
    li.appendChild(lvl);
    li.appendChild(body);
    list.insertBefore(li, list.firstChild);
    notifCount++;
    while (list.children.length > 40) list.removeChild(list.lastChild);
  }

  // ---------------------------------------------------------------- login
  function showLogin(show) {
    $("loginOverlay").classList.toggle("hidden", !show);
    if (show) setTimeout(function () { $("pinInput").focus(); }, 60);
  }

  function tryLogin() {
    var pin = $("pinInput").value;
    api("/api/login", "POST", { pin: pin }).then(function () {
      authed = true;
      $("pinError").classList.add("hidden");
      $("pinInput").value = "";
      showLogin(false);
      start();
      api("/api/me").then(function (me) {
        isAdmin = !!me.admin;
        if (me.setup_needed) showSetup();
      }).catch(function () {});
    }).catch(function () {
      $("pinError").classList.remove("hidden");
      $("pinInput").select();
    });
  }

  // ---------------------------------------------------------------- render
  var BANNER = {
    IDLE: ["PRONTO", "ready"],
    RECORDING: ["GRAVANDO", "recording"],
    FINALIZING: ["FINALIZANDO", "uploading"],
    UPLOADING: ["ENVIANDO", "uploading"],
    COMPLETED: ["PRONTO", "ready"],
    RECOVERY_REQUIRED: ["ATENCAO", "attention"],
    ERROR: ["ATENCAO", "error"]
  };

  function render() {
    if (!status) return;
    var st = status.state || "IDLE";
    var map = BANNER[st] || ["PRONTO", "ready"];
    var bannerText = status.banner && st !== "IDLE" && st !== "COMPLETED"
      ? status.banner : map[0];
    if (st === "IDLE" || st === "COMPLETED") bannerText = "PRONTO";

    $("banner").textContent = bannerText;
    var card = $("statusCard");
    card.className = "status-card " + map[1];
    $("stateDetail").textContent = status.detail ||
      (st === "IDLE" ? "Aguardando inicio" : map[0]);

    var rec = status.recording || {};
    var startedAt = rec.active ? rec.started_at : (st === "RECORDING" ? status.started_at : null);

    if (st === "RECORDING") {
      $("startTime").textContent = startedAt ? dataHora(startedAt) : "--";
      $("segmentCount").textContent = rec.segments || 0;
      $("fileSize").textContent = bytes(rec.bytes);
    } else {
      $("startTime").textContent = "--";
      $("segmentCount").textContent = "--";
      $("fileSize").textContent = "--";
    }
    card.dataset.started = startedAt || "";

    // botoes: acoes separadas, sem toggle
    var recovery = (status.recovery || []).length > 0;
    $("btnStart").disabled = (st === "RECORDING" || st === "FINALIZING" ||
                              st === "UPLOADING" || recovery);
    $("btnStop").disabled = (st !== "RECORDING");

    // armazenamento
    var disk = status.storage || {};
    if (disk.ok) {
      $("freeSpace").textContent = bytes(disk.free_mb * 1024 * 1024) + " livres";
      $("storagePath").textContent = disk.path;
      var pct = disk.used_percent || 0;
      $("storageBar").style.width = pct + "%";
      $("storageBar").className = pct > 90 ? "crit" : (pct > 75 ? "warn" : "");
      var summ = status.storage_detail || {};
      $("storageCount").textContent = (summ.count || 0) + " arquivo(s) gravado(s)";
    } else {
      $("freeSpace").textContent = "SEM DISCO";
      $("storagePath").textContent = disk.error || "verifique o armazenamento USB";
    }

    // destino de gravacao: com o SSD desmontado o diretorio configurado
    // continua existindo dentro do pasta do PC e a gravacao "funciona" la -
    // sem este aviso a troca passaria despercebida
    var avisoDestino = status.storage_aviso;
    var elAvisoDestino = $("storageAviso");
    if (elAvisoDestino) {
      elAvisoDestino.style.display = avisoDestino ? "" : "none";
      elAvisoDestino.textContent = avisoDestino || "";
      elAvisoDestino.style.color = avisoDestino ? "var(--amber)" : "";
    }

    // rede
    var online = status.network && status.network.online;
    $("networkState").textContent = online ? "ONLINE" : "OFFLINE";
    $("networkState").style.color = online ? "var(--green2)" : "var(--amber)";
    $("networkHint").textContent = online
      ? "internet disponivel" : "sem internet - as gravacoes ficam no PC";

    // audio
    var dev = status.device || {};
    $("audioDevice").textContent = dev.hw || "nao detectado";
    $("audioName").textContent = dev.name || "conecte a interface USB";

    // drive
    var drive = status.drive || {};
    var ups = status.uploads || {};
    if (!drive.libraries) {
      $("driveState").textContent = "NAO INSTALADO";
      $("driveHint").textContent = "bibliotecas do Google ausentes";
    } else if (!drive.credentials) {
      $("driveState").textContent = "NAO CONFIGURADO";
      $("driveState").style.color = "var(--amber)";
      $("driveHint").textContent = "solicitacao registrada - fale com o administrador";
    } else if (drive.connected) {
      $("driveState").textContent = "● CONECTADO";
      $("driveState").style.color = "var(--green2)";
      $("driveHint").textContent = (drive.account || "conta conectada") +
        (ups.online === false ? " · offline - fila aguardando internet"
                              : " · pronto para envio");
    } else {
      $("driveState").textContent = "DESCONECTADO";
      $("driveState").style.color = "var(--amber)";
      $("driveHint").textContent = "conecte em CONFIGURACOES";
    }
    $("uploadStats").textContent =
      "pendentes: " + (ups.pending || 0) + " | concluidos: " + (ups.done || 0);

    // ultima gravacao / upload
    var last = status.last_recording;
    if (last && last.final_path) {
      $("lastFile").textContent = last.final_path.split(/[\\/]/).pop();
      $("lastFileMeta").textContent =
        bytes(last.final_bytes) + " · " + (last.state || "") +
        (last.ended_at ? " · " + dataHora(last.ended_at) : "");
    } else {
      $("lastFile").textContent = "nenhuma gravacao";
      $("lastFileMeta").textContent = "";
    }
    $("lastUpload").textContent = ups.last_upload
      ? "ultimo upload: " + ups.last_upload.file + " [ok]"
      : (ups.last_error ? "ultimo erro: " + ups.last_error : "");

    $("deviceName").textContent = status.device_name || "pregacao-recorder";
    // saude e progresso do estudo acompanham o estado atual do servidor.
    if (status.estudos) pintaNlm(status.estudos);
    if (status.estudos && status.estudos.barra) {
      pintaProgresso(status.estudos.barra);
    }
    renderRecovery(status.recovery || []);
    tick();
  }

  function renderRecovery(items) {
    var panel = $("recoveryPanel");
    if (!items.length) { panel.classList.add("hidden"); return; }
    panel.classList.remove("hidden");
    var box = $("recoveryList");
    box.innerHTML = "";
    items.forEach(function (item) {
      var div = document.createElement("div");
      div.className = "recovery-item";
      var row = document.createElement("div");
      row.className = "row";
      row.innerHTML =
        "<span><strong>Inicio:</strong> " + item.started_label + "</span>" +
        "<span><strong>Duracao recuperada:</strong> " + hms(item.duration) + "</span>" +
        "<span><strong>Tamanho:</strong> " + bytes(item.bytes) + "</span>" +
        "<span><strong>Segmentos:</strong> " + item.segments + "</span>";
      div.appendChild(row);
      if (item.error) {
        var err = document.createElement("p");
        err.className = "muted";
        err.style.margin = "6px 0 0";
        err.textContent = "Motivo: falha na conversao - " + item.error;
        div.appendChild(err);
      }
      var btns = document.createElement("div");
      btns.className = "btn-row";
      var rec = document.createElement("button");
      rec.className = "btn btn-primary";
      rec.type = "button";
      rec.textContent = "RECUPERAR";
      rec.onclick = function () {
        rec.disabled = true; rec.textContent = "RECUPERANDO...";
        api("/api/recovery/" + encodeURIComponent(item.id) + "/recover", "POST")
          .then(function () { toast("Recuperando a gravacao...", "success"); })
          .catch(function (e) { toast(e.message, "error"); rec.disabled = false; });
      };
      var disc = document.createElement("button");
      disc.className = "btn btn-ghost";
      disc.type = "button";
      disc.textContent = "DESCARTAR";
      disc.onclick = function () {
        if (!window.confirm("Descartar definitivamente esta gravacao interrompida?")) return;
        api("/api/recovery/" + encodeURIComponent(item.id) + "/discard", "POST")
          .then(function () { toast("Gravacao descartada", "warning"); })
          .catch(function (e) { toast(e.message, "error"); });
      };
      btns.appendChild(rec);
      btns.appendChild(disc);
      div.appendChild(btns);
      box.appendChild(div);
    });
  }

  function esc(t) {
    return String(t === null || t === undefined ? "" : t)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  // ------------------------------------------------------------- historico
  var STATE_PT = {
    IDLE: "PRONTO", RECORDING: "GRAVANDO", FINALIZING: "FINALIZANDO",
    UPLOADING: "ENVIANDO", COMPLETED: "CONCLUIDA",
    RECOVERY_REQUIRED: "INTERROMPIDA", ERROR: "ERRO"
  };

  function loadHistory() {
    $("histSummary").textContent = "carregando...";
    api("/api/recordings").then(function (data) {
      var sessions = data.sessions || [];
      var summ = data.summary || {};
      var list = $("histList");
      list.innerHTML = "";
      $("histSummary").textContent = (summ.count || 0) + " arquivo(s) · " +
        bytes(summ.bytes || 0) + " gravados em disco";
      if (!sessions.length) {
        list.innerHTML = "<p class='muted'>Nenhuma gravacao registrada ainda.</p>";
        return;
      }
      sessions.forEach(function (s) {
        var div = document.createElement("div");
        div.className = "histitem";
        var upload = s.drive_file_id
          ? "<span class='tag ok'>ENVIADO</span>"
          : "<span class='tag pend'>PENDENTE</span>";
        var drive = s.drive_path ? esc(s.drive_path) : "aguardando envio";
        var statusTxt = (STATE_PT[s.state] || s.state || "--") +
          (s.interrupted ? " (recuperada)" : "");
        div.innerHTML =
          "<div class='histdate'>" + dataHora(s.started_at) + "</div>" +
          "<div class='histmeta'>" +
            "<span><strong>Duracao:</strong> " + hms(s.duration_secs || 0) + "</span>" +
            "<span><strong>Tamanho:</strong> " + bytes(s.final_bytes || s.bytes) + "</span>" +
            "<span><strong>Status:</strong> " + esc(statusTxt) + "</span>" +
            "<span><strong>Upload:</strong> " + upload + "</span>" +
            "<span><strong>Google Drive:</strong> " + drive + "</span>" +
          "</div>";
        if (s.error) {
          var err = document.createElement("p");
          err.className = "muted";
          err.textContent = "Erro: " + s.error;
          div.appendChild(err);
        }
        list.appendChild(div);
      });
    }).catch(function (e) { $("histSummary").textContent = e.message; });
  }

  // ---------------------------------------------------------------- tempo
  function tick() {
    var started = Number($("statusCard").dataset.started || 0);
    if (status && status.state === "RECORDING" && started) {
      var now = (Date.now() / 1000) + clockOffset;
      $("timer").textContent = hms(now - started);
    } else {
      $("timer").textContent = "00:00:00";
    }
    var d = new Date();
    $("clock").textContent = pad(d.getHours()) + ":" + pad(d.getMinutes());
  }
  setInterval(tick, 1000);

  // ---------------------------------------------------------------- acoes
  function doStart() {
    api("/api/start", "POST").then(function () {
      toast("Gravacao iniciada", "success");
      addNotif("Gravacao iniciada", "success");
    }).catch(function (e) { toast(e.message, "error"); });
  }

  function askStop() {
    var st = status || {};
    var rec = st.recording || {};
    $("confirmDetail").textContent =
      "Duracao atual: " + $("timer").textContent +
      (rec.segments ? " · segmentos: " + rec.segments : "") +
      ". Depois de confirmada, a gravacao sera consolidada e salva.";
    $("confirmOverlay").classList.remove("hidden");
  }

  function doStop() {
    $("confirmOverlay").classList.add("hidden");
    $("btnStop").disabled = true;
    api("/api/stop", "POST").then(function () {
      toast("Finalizando gravacao...", "success");
      addNotif("Gravacao finalizada; consolidando arquivos", "success");
    }).catch(function (e) { toast(e.message, "error"); refresh(); });
  }

  function refresh() {
    return api("/api/status").then(function (data) {
      status = data;
      clockOffset = (data.now || Date.now() / 1000) - Date.now() / 1000;
      render();
    }).catch(function () {});
  }

  // ---------------------------------------------------------------- SSE
  function connect() {
    if (!window.EventSource) { setInterval(refresh, 5000); return; }
    if (source) source.close();
    source = new EventSource("/api/stream");

    source.addEventListener("open", function () {
      $("connState").textContent = "● conectado";
      $("connState").className = "ok";
    });
    source.addEventListener("error", function () {
      $("connState").textContent = "● reconectando";
      $("connState").className = "bad";
    });
    source.addEventListener("job_progress", onJobProgress);
    source.addEventListener("status", function (ev) {
      try {
        var data = JSON.parse(ev.data);
        if (data.state !== undefined) {
          status = data;
          if (data.now) clockOffset = data.now - Date.now() / 1000;
          render();
        }
      } catch (e) { /* ignora */ }
    });

    ["gravacao_iniciada", "gravacao_finalizada", "gravacao_pronta",
     "upload_inicio", "upload_concluido", "upload_pendente", "upload_falho", "erro",
     "recuperacao", "recuperacao_descartada", "servico_parado", "capture_gap",
     "configuracao", "drive_conectado", "drive_desconectado", "audio_teste",
     "programacao_alterada",
     "conversao", "notificacao", "job_progress"].forEach(function (kind) {
      source.addEventListener(kind, function (ev) {
        try {
          var payload = JSON.parse(ev.data);
          var data = payload.data || {};
          if (data.message) {
            addNotif(data.message, data.level || "info", payload.ts);
            if (kind !== "upload_inicio" && kind !== "conversao") {
              toast(data.message, data.level || "info");
            }
          }
        } catch (e) { /* ignora */ }
        if (kind === "programacao_alterada" && authed) loadPregacoes();
        refresh();
      });
    });
  }

  // ---------------------------------------------------------------- progresso do estudo (S3)
  function pintaProgresso(b) {
    var card = $("progressoCard");
    if (!card) return;
    if (!b || !b.mostrar) { card.classList.add("hidden"); return; }
    card.classList.remove("hidden");
    var bar = $("progressoBar");
    var pct = Math.max(0, Math.min(100, Number(b.percentual) || 0));
    if (bar) bar.style.width = pct + "%";
    var desc = $("progressoDesc");
    if (desc) desc.textContent = pct + "% - " + (b.descricao || "");
    var et = $("progressoEtapas");
    if (et) {
      et.innerHTML = "";
      (b.etapas || []).forEach(function (e) {
        var s = document.createElement("span");
        s.className = "etapa tom-" + (e.tom || "pendente");
        s.textContent = e.nome;
        et.appendChild(s);
      });
    }
  }

  // handler SSE dedicado: atualiza a barra na hora + refresh para trazer a barra completa
  function onJobProgress(ev) {
    try {
      var payload = JSON.parse(ev.data);
      var data = payload.data || {};
      if (data.percentual != null || data.etapa) {
        // snapshot imediato do payload (para feedback rapido no celular/painel)
        var b = {
          mostrar: true,
          percentual: data.percentual || 0,
          descricao: data.descricao || data.etapa || "",
          etapas: [] // render() vai preencher a partir de /api/status
        };
        pintaProgresso(b);
      }
    } catch (e) {}
    refresh();
  }

  // ---------------------------------------------------------------- config
  function fillSelect(sel, options, current) {
    sel.innerHTML = "";
    options.forEach(function (opt) {
      var o = document.createElement("option");
      if (typeof opt === "object") { o.value = opt.value; o.textContent = opt.label; }
      else { o.value = opt; o.textContent = opt; }
      if (typeof opt === "object" && opt.disabled) o.disabled = true;
      if (String(opt.value !== undefined ? opt.value : opt) === String(current)) o.selected = true;
      sel.appendChild(o);
    });
  }

  // Preenche o seletor "Onde gravar" com os destinos que ESTAO disponiveis
  // agora. Enumerar discos do Windows e medir espaco e trabalho do servidor - aqui so
  // recebemos o resultado pronto de /api/storage. Destino com disco ausente
  // fica visivel (para o usuario entender o aviso) mas marcado como
  // indisponivel, igualzinho o servidor recusa ao salvar.
  function carregaDestinos(selecionado) {
    var sel = $("cfgDestino");
    if (!sel) return;
    api("/api/storage").then(function (r) {
      var itens = (r.items || []).slice();
      selecionado = selecionado || r.current;
      if (selecionado && !itens.some(function (i) { return i.caminho === selecionado; })) {
        itens.unshift({ caminho: selecionado, rotulo: "destino digitado",
                        montado: false, externo: false, disco: {} });
      }
      fillSelect(sel, itens.map(function (i) {
        var disco = i.disco || {};
        var livre = disco.livre_gb != null ? disco.livre_gb + " GB livres" : "";
        var sufixo;
        if (!i.montado) sufixo = "  -  DISCO AUSENTE";
        else if (i.externo) sufixo = "  -  " + (i.rotulo ? i.rotulo + " - " : "") + livre;
        else sufixo = "  -  " + (i.rotulo || "pasta do PC") + " - " + livre;
        return { value: i.caminho, label: i.caminho + sufixo, disabled: !i.montado };
      }), selecionado);

      var aviso = r.aviso;
      var elAviso = $("cfgDestinoAviso");
      if (elAviso) {
        elAviso.style.display = aviso ? "" : "none";
        elAviso.textContent = aviso || "";
        elAviso.style.color = aviso ? "var(--amber)" : "";
      }
      var sit = r.situacao || {};
      var elInfo = $("cfgDestinoInfo");
      if (elInfo) {
        elInfo.textContent = sit.disponivel
          ? "gravando em " + r.current
            + (sit.device ? " (" + sit.device + ")" : "")
          : "destino atual fora do lugar - escolha outro ou reconecte o disco";
      }
    }).catch(function () {
      // sem /api/storage o select fica vazio: nao e motivo de quebrar a tela
    });
  }

  function pintaNlm(p) {
    var el = $("cfgNlmState");
    if (!el) return;
    p = p || {};
    nlmUltimo = p;
    var login = p.login || {};
    var ocupado = nlmLoginPedido || nlmDiagnostico || !!login.em_andamento;
    var mapa = {
      ok: ["● SESSAO ATIVA", "var(--green2)"],
      auth: ["○ SESSAO EXPIRADA", "var(--amber)"],
      rede: ["○ SEM RESPOSTA", "var(--amber)"],
      desconhecido: ["○ NAO VERIFICADA", "var(--amber)"]
    };
    var m = mapa[p.estado] || mapa.desconhecido;
    var orientacao = "Para renovar o login, entre na sua conta na janela do navegador do PC.";
    if (nlmLoginPedido || login.em_andamento) {
      var fases = {
        abrindo: "ABRINDO LOGIN",
        aguardando: "AGUARDANDO LOGIN NO PC",
        verificando: "VERIFICANDO LOGIN"
      };
      el.textContent = fases[login.estado] || "ABRINDO LOGIN";
      el.style.color = "var(--amber)";
      orientacao = login.estado === "verificando"
        ? "Login recebido. Aguarde a confirmacao da sessao; o painel atualiza sozinho."
        : "Entre na sua conta na janela do navegador do PC e conclua o login. O painel confirma quando estiver pronto.";
    } else if (nlmDiagnostico) {
      el.textContent = "VERIFICANDO SESSAO";
      el.style.color = "var(--amber)";
      orientacao = "Verificando a sessao do NotebookLM. Aguarde o resultado.";
    } else if (login.estado === "erro") {
      el.textContent = "LOGIN NAO CONCLUIDO";
      el.style.color = "var(--red2)";
      orientacao = login.detalhe || "Nao foi possivel confirmar o login. Tente renovar novamente no navegador do PC.";
    } else if (p.aguardando) {
      el.textContent = "● AGUARDANDO: " + (p.motivo || "sessao");
      el.style.color = "var(--amber)";
    } else {
      el.textContent = m[0];
      el.style.color = m[1];
    }
    if (!ocupado && login.estado === "concluido" && p.estado === "ok") {
      orientacao = "Login confirmado. " + (login.retomados
        ? login.retomados + " estudo(s) retomado(s)."
        : "A sessao do NotebookLM esta ativa.");
    }
    var mensagem = $("cfgNlmLogin");
    if (mensagem) mensagem.textContent = orientacao;
    var pend = $("cfgNlmPend");
    if (pend) {
      pend.textContent = p.aguardando
        ? p.aguardando + " em espera (nada perdido)"
        : (p.fila ? p.fila + " na fila" : "nenhum");
    }
    // acoes que mexem no PC so para o administrador (o servidor tambem
    // bloqueia - aqui e so para o operador comum nao se confundir)
    var b1 = $("btnNlmCheck");
    var b2 = $("btnNlmLogin");
    var acao = isAdmin ? "" : "none";
    if (b1) { b1.style.display = acao; b1.disabled = ocupado; }
    if (b2) { b2.style.display = acao; b2.disabled = ocupado; }
  }

  // ---------------------------------------------------------------- saude das integracaoes (S3)
  function estadoParaClasse(estado) {
    // conectado / nao_configurado / verificando / autenticacao_necessaria / erro
    switch (estado) {
      case "conectado": return "conectado";
      case "nao_configurado": return "nao_configurado";
      case "verificando": return "verificando";
      case "autenticacao_necessaria": return "autenticacao_necessaria";
      case "erro": return "erro";
      default: return "verificando";
    }
  }

  function pintaIntegracao(el, bloco) {
    var dotClass = estadoParaClasse(bloco.estado);
    el.innerHTML =
      "<div class='integracoes-head'>" +
      "  <span class='integracoes-dot " + dotClass + "'></span>" +
      "  <span class='integracoes-name'>" + bloco.nome + "</span>" +
      "</div>" +
      "<div class='integracoes-detalhe'>" + (bloco.detalhe || "") + "</div>" +
      (bloco.acao ? "<span class='integracoes-acao'>" + bloco.acao + "</span>" : "");
  }

  function loadIntegracoes() {
    var box = $("integracoesLista");
    if (!box) return;
    api("/api/integracoes").then(function (data) {
      if (!data) { box.textContent = "sem dados"; return; }
      box.innerHTML = "";
      var grid = document.createElement("div");
      grid.className = "integracoes-grid";
      var ordem = ["Drive", "NotebookLM", "WhatsApp", "EMQX"];
      var chaves = ["drive", "notebooklm", "whatsapp", "emqx"];
      for (var i = 0; i < ordem.length; i++) {
        var key = chaves[i];
        var bloco = data[key];
        if (!bloco) continue;
        var item = document.createElement("div");
        item.className = "integracoes-item";
        bloco.nome = ordem[i];
        pintaIntegracao(item, bloco);
        grid.appendChild(item);
      }
      box.appendChild(grid);
    }).catch(function (e) {
      box.textContent = "falha ao carregar: " + e.message;
    });
  }

  function renderRemotePairing(data) {
    var allowed = !!(data && data.admin === true && document.body.dataset.view === "advanced");
    var remote = allowed ? (data.remote || {}) : {};
    $("cfgRemoteCard").classList.toggle("hidden", !allowed);
    $("cfgRemoteDevice").textContent = remote.device_id || "--";
    $("cfgRemoteHost").textContent = remote.host || "nao configurado";
    $("cfgRemotePort").textContent = allowed ? String(remote.port || 8883) : "--";
    $("cfgRemoteTls").textContent = allowed ? (remote.tls ? "SIM" : "NAO") : "--";
    $("cfgRemoteEnabled").checked = !!remote.enabled;
    $("cfgRemoteHostInput").value = remote.host || "";
    $("cfgRemotePortInput").value = allowed ? String(remote.port || 8883) : "";
    $("cfgRemoteTlsInput").checked = !!remote.tls;
    $("cfgRemoteUsername").value = remote.username || "";
    $("cfgRemoteDeviceInput").value = remote.device_id || "";
    $("cfgRemotePassword").value = "";
    $("cfgRemotePassword").placeholder = remote.password_configured
      ? "(senha definida - em branco preserva)" : "(senha nao definida)";
    $("cfgRemoteNewToken").value = "";
    $("cfgRemoteMessage").textContent = remote.restart_required
      ? "Alteracoes salvas. Aguarde terminar gravacoes e filas, reinicie o Windows e abra o atalho. Depois confirme STATUS/ACK no celular."
      : "";
    var token = $("cfgRemoteToken");
    token.type = "password";
    token.value = remote.operator_token || "";
    $("btnRemoteToken").disabled = !token.value;
    $("btnRemoteToken").textContent = "MOSTRAR TOKEN";
    $("btnRemoteToken").setAttribute("aria-pressed", "false");
  }

  function toggleRemoteToken() {
    var token = $("cfgRemoteToken");
    if (!isAdmin || !token.value) return;
    var reveal = token.type === "password";
    token.type = reveal ? "text" : "password";
    $("btnRemoteToken").textContent = reveal ? "OCULTAR TOKEN" : "MOSTRAR TOKEN";
    $("btnRemoteToken").setAttribute("aria-pressed", String(reveal));
  }

  function saveRemoteConfig() {
    if (!isAdmin) { openAdmin(); return; }
    var button = $("btnRemoteSave");
    var msg = $("cfgRemoteMessage");
    var payload = {
      enabled: $("cfgRemoteEnabled").checked,
      host: $("cfgRemoteHostInput").value.trim(),
      port: Number($("cfgRemotePortInput").value),
      tls: $("cfgRemoteTlsInput").checked,
      username: $("cfgRemoteUsername").value.trim(),
      device_id: $("cfgRemoteDeviceInput").value.trim()
    };
    // Segredos em branco sao omitidos; a senha atual nunca vem do servidor.
    if ($("cfgRemotePassword").value) payload.password = $("cfgRemotePassword").value;
    if ($("cfgRemoteNewToken").value.trim()) payload.operator_token = $("cfgRemoteNewToken").value.trim();
    button.disabled = true;
    msg.textContent = "salvando...";
    return api("/api/remote/config", "POST", payload).then(function (r) {
      renderRemotePairing({admin: true, remote: r.remote});
      if (document.body.dataset.view === "advanced") {
        msg.textContent = r.message || msg.textContent || "Controle remoto salvo";
      }
      toast("Controle remoto salvo", "success");
    }).catch(function (e) {
      msg.textContent = e.message;
      toast(e.message, "error");
      if (e.data && e.data.error === "admin_obrigatorio") openAdmin();
    }).finally(function () { button.disabled = false; });
  }

  function testSelectedAudio(resultId, buttonId, payload) {
    var el = $(resultId);
    var button = $(buttonId);
    button.disabled = true;
    el.textContent = "testando (2s)...";
    return api("/api/audio/test", "POST", payload).then(function (r) {
      if (!r.ok) { el.textContent = "FALHA: " + r.error; return; }
      var device = r.device || {};
      var nome = device.name || device.hw || (payload && payload.device) || "";
      el.textContent = (nome ? nome + ": " : "") + (r.silent
        ? "SILENCIO - suba o fader da mesa"
        : "Sinal OK - pico " + r.peak_db + " dBFS");
    }).catch(function (e) {
      el.textContent = e.message;
      if (e.data && e.data.error === "admin_obrigatorio") {
        if (buttonId === "wizAudioTest") openWizAdmin();
        else openAdmin();
      }
    }).finally(function () { button.disabled = false; });
  }

  function loadConfig() {
    api("/api/config").then(function (data) {
      var c = data.config || {};
      $("configForm").elements["device_name"].value = c.device_name || "";
      // usuario comum recebe "estudos" no topo; admin traz dentro de config
      var est = data.estudos || c.estudos || {};
      $("configForm").elements["estudos.ativo"].checked = est.ativo !== false;
      $("configForm").elements["estudos.whatsapp"].value = est.whatsapp || "";

      // card ESTUDO: saude da sessao do NotebookLM (consulta propria,
      // independente do Drive - sao autenticacoes diferentes)
      api("/api/estudos/status").then(pintaNlm).catch(function () {
        // sem /api/estudos/status o card fica com "--" e nada mais quebra
      });

      // card GOOGLE DRIVE (usuario comum nunca ve credenciais)
      var d = data.drive || {};
      if (d.connected) {
        $("cfgDriveState").textContent = "● CONECTADO";
        $("cfgDriveState").style.color = "var(--green2)";
      } else if (!d.credentials) {
        $("cfgDriveState").textContent = "○ NAO CONFIGURADO";
        $("cfgDriveState").style.color = "var(--amber)";
      } else {
        $("cfgDriveState").textContent = "○ NAO CONECTADO";
        $("cfgDriveState").style.color = "var(--amber)";
      }
      $("cfgDriveAccount").textContent = d.connected
        ? (d.account || "conta conectada")
        : (d.credentials ? "conecte a conta Google" : "aguardando o administrador");
      $("cfgDriveFolder").textContent = d.folder || "Pregacoes";
      // o payload completo (credenciais/formatos) so vem para administrador
      if (data.admin) loadAdvanced(data);
      else renderRemotePairing(null);
      loadIntegracoes();
    }).catch(function (e) { toast(e.message, "error"); });
  }

  function loadAdvanced(data) {
    var apply = function (data) {
      renderRemotePairing(data);
      if (!data.admin) return;
      var c = data.config || {};
      var form = $("advancedForm");

      var audioOptions = [{ value: "auto", label: "AUTO (detectar interface USB)" }].concat(
          (data.audio_devices || []).map(function (d) {
            return { value: d.hw, label: d.hw + " - " + d.name };
          }));
      if (c.audio.device && !audioOptions.some(function (opt) { return opt.value === c.audio.device; })) {
        audioOptions.push({value: c.audio.device, label: c.audio.device + " (indisponivel - reconecte a interface)"});
      }
      fillSelect($("cfgDevice"), audioOptions, c.audio.device);
      fillSelect($("cfgFormat"), data.formats || [], c.audio.format);
      fillSelect($("cfgRate"), data.rates || [], c.audio.sample_rate);
      fillSelect($("cfgEncoder"), data.encoders || [], c.audio.encoder);
      fillSelect($("cfgBitrate"), data.bitrates || [], c.audio.bitrate);
      $("cfgDeviceDetected").textContent = data.detected
        ? "detectado: " + data.detected.hw + " - " + data.detected.name
        : "";
      $("cfgFfmpeg").textContent = data.has_ffmpeg
        ? "ffmpeg disponivel: a gravacao final sera MP3."
        : "ffmpeg ausente: instale-o para habilitar captura e conversao no Windows.";

      form.elements["audio.channels"].value = String(c.audio.channels);
      form.elements["audio.segment_seconds"].value = c.audio.segment_seconds;
      var destinoAtual = c.storage.recordings_dir || "";
      form.elements["storage.recordings_dir"].value = destinoAtual;
      carregaDestinos(destinoAtual);  // opcoes reais vem de /api/storage
      form.elements["storage.min_free_mb"].value = c.storage.min_free_mb;
      form.elements["storage.retention_days"].value = c.storage.retention_days;
      form.elements["drive.enabled"].checked = !!c.drive.enabled;
      form.elements["drive.auto_upload"].checked = !!c.drive.auto_upload;
      form.elements["drive.keep_local"].checked = !!c.drive.keep_local;
      form.elements["drive.folder_name"].value = c.drive.folder_name || "Pregacoes";
      form.elements["drive.client_id"].value = c.drive.client_id || "";
      form.elements["network.check_host"].value =
        (c.network && c.network.check_host) || "";
      form.elements["network.check_port"].value =
        (c.network && c.network.check_port) || 443;
      form.elements["network.retry_seconds"].value =
        (c.network && c.network.retry_seconds) || 30;
      var secretInput = form.elements["drive.client_secret"];
      secretInput.value = "";
      secretInput.placeholder = c.drive.client_secret_set
        ? "(secret definido - digite apenas para trocar)"
        : "(secret nao definido)";

      var d = data.drive || {};
      var srcLabel = {
        manual: "cadastradas NA INTERFACE",
        arquivo: "no arquivo google_credentials.json",
        env: "na variavel .env",
        "": "AUSENTES"
      };
      $("cfgDriveCreds").textContent = "Credenciais: "
        + (srcLabel[d.source] !== undefined ? srcLabel[d.source] : d.source);

    };
    if (data) apply(data);
    else api("/api/config").then(apply).catch(function (e) { toast(e.message, "error"); });
  }

  // ================================================================
  // S4: PROGRAMACAO DE PREGACOES (CRUD + IMPORTACAO)
  // ================================================================
  var _pregacoesCache = [];
  var _importacaoCache = [];
  var _pregacaoEditada = null;

  function loadPregacoes() {
    api("/api/pregacoes").then(function (r) {
      _pregacoesCache = r.pregacoes || [];
      renderPregacoes();
    }).catch(function (e) {
      toast(e.message, "error");
    });
  }

  function renderPregacoes() {
    var list = $("pregacoesList");
    if (!list) return;
    ["btnAddPregacao", "btnImportPregacao", "btnDownloadModelo"].forEach(function (id) {
      $(id).classList.toggle("hidden", !isAdmin);
    });
    $("btnScheduleAdmin").classList.toggle("hidden", isAdmin);
    if (!_pregacoesCache.length) {
      list.innerHTML = "<li class='muted'>Nenhuma pregacao cadastrada</li>";
      return;
    }
    list.innerHTML = "";
    var hoje = new Date();
    var corte = hoje.getFullYear() + "-" + String(hoje.getMonth() + 1).padStart(2, "0") +
      "-" + String(hoje.getDate()).padStart(2, "0");
    var proximas = _pregacoesCache.filter(function (p) { return p.data >= corte; })
      .sort(function (a, b) { return (a.data + a.horario).localeCompare(b.data + b.horario); });
    var anteriores = _pregacoesCache.filter(function (p) { return p.data < corte; })
      .sort(function (a, b) { return (b.data + b.horario).localeCompare(a.data + a.horario); });
    proximas.concat(anteriores).forEach(function (p) {
      var li = document.createElement("li");
      li.innerHTML =
        "<strong>" + esc(p.data) + " " + esc(p.horario) + "</strong>  " +
        esc(p.pregador) + " / " + esc(p.igreja) +
        (p.texto_base ? " · " + esc(p.texto_base) : "") +
        (p.tema ? " · " + esc(p.tema) : "");
      if (!isAdmin) { list.appendChild(li); return; }
      var btns = document.createElement("div");
      btns.style.marginTop = "4px";
      var editar = document.createElement("button");
      editar.className = "btn btn-ghost btn-sm";
      editar.type = "button";
      editar.textContent = "EDITAR";
      editar.onclick = function () { openPregacaoModal(p); };
      var excluir = document.createElement("button");
      excluir.className = "btn btn-ghost btn-sm";
      excluir.type = "button";
      excluir.textContent = "EXCLUIR";
      excluir.style.color = "var(--red2)";
      excluir.style.borderColor = "var(--red2)";
      excluir.onclick = function () {
        if (!confirm("Excluir pregacao de " + p.data + " " + p.horario + "?")) return;
        api("/api/pregacoes/" + p.id, "DELETE", { versao: p.versao }).then(function () {
          toast("Pregacao excluida", "success");
          loadPregacoes();
        }).catch(function (e) { toast(e.message, "error"); loadPregacoes(); });
      };
      btns.appendChild(editar);
      btns.appendChild(excluir);
      li.appendChild(btns);
      list.appendChild(li);
    });
  }

  function openPregacaoModal(p) {
    var overlay = $("pregacaoOverlay");
    var form = $("pregacaoForm");
    var title = $("pregacaoOverlayTitle");
    form.reset();
    _pregacaoEditada = p;
    if (p) {
      title.textContent = "EDITAR PREGACAO";
      $("pregacaoId").value = p.id;
      form.elements["data"].value = p.data;
      form.elements["horario"].value = p.horario;
      form.elements["pregador"].value = p.pregador;
      form.elements["igreja"].value = p.igreja;
      form.elements["texto_base"].value = p.texto_base || "";
      form.elements["tema"].value = p.tema || "";
    } else {
      title.textContent = "NOVA PREGACAO";
      $("pregacaoId").value = "";
      var hoje = new Date();
      var dataPadrao = hoje.getFullYear() + "-" +
        String(hoje.getMonth() + 1).padStart(2, "0") + "-" +
        String(hoje.getDate()).padStart(2, "0");
      form.elements["data"].value = dataPadrao;
      form.elements["horario"].value = "19:00";
    }
    overlay.classList.remove("hidden");
    setTimeout(function () { form.elements["pregador"].focus(); }, 60);
  }

  function closePregacaoModal() {
    $("pregacaoOverlay").classList.add("hidden");
    $("pregacaoForm").reset();
    _pregacaoEditada = null;
  }

  function savePregacao(ev) {
    ev.preventDefault();
    var form = $("pregacaoForm");
    var id = form.elements["id"].value;
    var payload = {
      data: form.elements["data"].value,
      horario: form.elements["horario"].value,
      pregador: form.elements["pregador"].value.trim(),
      igreja: form.elements["igreja"].value.trim(),
      texto_base: form.elements["texto_base"].value.trim(),
      tema: form.elements["tema"].value.trim(),
    };
    if (id && _pregacaoEditada) payload.versao = _pregacaoEditada.versao;
    var url = id ? "/api/pregacoes/" + id : "/api/pregacoes";
    var method = id ? "PUT" : "POST";
    var msg = $("pregacaoMsg");
    msg.textContent = "salvando...";
    api(url, method, payload).then(function () {
      msg.textContent = "";
      toast(id ? "Pregacao atualizada" : "Pregacao criada", "success");
      closePregacaoModal();
      loadPregacoes();
    }).catch(function (e) {
      msg.textContent = e.message;
      toast(e.message, "error");
      if (e.data && e.data.error === "versao_desatualizada") {
        closePregacaoModal();
        loadPregacoes();
      }
    });
  }

  // ----- IMPORTACAO CSV/XLSX -----
  function openImportModal() {
    $("importOverlay").classList.remove("hidden");
    _importacaoCache = [];
    $("importFile").value = "";
    $("importPreview").style.display = "none";
    $("importPreview").textContent = "";
    $("importMsg").textContent = "";
    $("importConfirm").disabled = true;
  }

  function closeImportModal() {
    $("importOverlay").classList.add("hidden");
  }

  function previewImport(ev) {
    var file = ev.target.files[0];
    if (!file) return;
    var formData = new FormData();
    formData.append("arquivo", file);
    var msg = $("importMsg");
    msg.textContent = "lendo...";
    fetch("/api/importacao/previa", {
      method: "POST", body: formData, credentials: "same-origin"
    }).then(function (resp) {
      return resp.json().catch(function () { return {}; }).then(function (data) {
        if (!resp.ok) {
          msg.textContent = data.message || "falha na leitura";
          throw new Error(data.message);
        }
        var v = data.validos || [];
        var e = data.erros || [];
        var d = data.duplicatas || [];
        var partes = [];
        if (v.length) partes.push(v.length + " valido(s)");
        if (e.length) partes.push(e.length + " erro(s)");
        if (d.length) partes.push(d.length + " duplicata(s)");
        msg.textContent = partes.join(" · ") || "vazio";
        if (v.length) {
          var linhas = v.slice(0, 5).map(function (p) {
            return p.data + " " + p.horario + " · " + p.pregador + " / " + p.igreja;
          }).join("\n");
          if (v.length > 5) linhas += "\n... e mais " + (v.length - 5);
          $("importPreview").textContent = "Validos:\n" + linhas;
          $("importPreview").style.display = "block";
        }
        if (e.length || d.length) {
          _importacaoCache = v; // guarda para confirmar
          $("importConfirm").disabled = false;
        } else {
          _importacaoCache = v;
          $("importConfirm").disabled = v.length === 0;
        }
      });
    }).catch(function () {});
  }

  function confirmImport() {
    if (!_importacaoCache.length) return;
    var msg = $("importMsg");
    msg.textContent = "gravando...";
    api("/api/importacao/confirmar", "POST", { validos: _importacaoCache })
      .then(function () {
        msg.textContent = "";
        toast("Importacao concluida", "success");
        closeImportModal();
        loadPregacoes();
      }).catch(function (e) {
        msg.textContent = e.message;
        toast(e.message, "error");
      });
  }

  function downloadModelo() {
    // o link ja aponta para /api/importacao/modelo via atributo download
    // mas forca o fetch se o navegador nao respeitar
    api("/api/importacao/modelo").then(function (blob) {
      // Response blob handling for browsers that ignore download attr on <a>
      var url = window.URL.createObjectURL(blob);
      var a = document.createElement("a");
      a.href = url; a.download = "modelo_pregacoes.csv"; a.click();
      window.URL.revokeObjectURL(url);
    }).catch(function () {});
  }

  function saveConfig(ev) {
    ev.preventDefault();
    var form = $("configForm");
    var payload = {
      "device_name": form.elements["device_name"].value,
      "estudos.ativo": form.elements["estudos.ativo"].checked,
      "estudos.whatsapp": form.elements["estudos.whatsapp"].value.trim()
    };
    var msg = $("configMsg");
    msg.textContent = "salvando...";
    api("/api/config", "POST", payload).then(function (res) {
      msg.textContent = "Configuracao salva";
      toast("Configuracao salva", "success");
      addNotif("Configuracao atualizada", "success");
      loadConfig();
    }).catch(function (e) {
      msg.textContent = "";
      toast(e.message, "error");
    });
  }

  function saveAdvanced(ev) {
    ev.preventDefault();
    var form = $("advancedForm");
    var payload = {
      "audio.device": form.elements["audio.device"].value,
      "audio.format": form.elements["audio.format"].value,
      "audio.sample_rate": form.elements["audio.sample_rate"].value,
      "audio.channels": form.elements["audio.channels"].value,
      "audio.encoder": form.elements["audio.encoder"].value,
      "audio.bitrate": form.elements["audio.bitrate"].value,
      "audio.segment_seconds": form.elements["audio.segment_seconds"].value,
      "storage.recordings_dir": form.elements["storage.recordings_dir"].value,
      "storage.min_free_mb": form.elements["storage.min_free_mb"].value,
      "storage.retention_days": form.elements["storage.retention_days"].value,
      "drive.enabled": form.elements["drive.enabled"].checked,
      "drive.auto_upload": form.elements["drive.auto_upload"].checked,
      "drive.keep_local": form.elements["drive.keep_local"].checked,
      "drive.folder_name": form.elements["drive.folder_name"].value,
      "drive.client_id": form.elements["drive.client_id"].value.trim(),
      "network.check_host": form.elements["network.check_host"].value.trim(),
      "network.check_port": form.elements["network.check_port"].value,
      "network.retry_seconds": form.elements["network.retry_seconds"].value
    };
    // o secret so vai para o servidor quando digitado (nunca e devolvido)
    var secret = form.elements["drive.client_secret"].value.trim();
    if (secret) payload["drive.client_secret"] = secret;
    var msg = $("advancedMsg");
    msg.textContent = "salvando...";
    api("/api/config", "POST", payload).then(function () {
      msg.textContent = "Configuracoes avancadas salvas";
      toast("Configuracoes avancadas salvas", "success");
      loadAdvanced();
      loadConfig();
    }).catch(function (e) {
      msg.textContent = "";
      toast(e.message, "error");
      if (e.data && e.data.error === "admin_obrigatorio") openAdmin();
    });
  }

  // ---------------------------------------------------------------- admin
  function openAdmin(returnView) {
    adminReturnView = returnView || "advanced";
    $("adminPinError").classList.add("hidden");
    $("adminPinInput").value = "";
    $("adminOverlay").classList.remove("hidden");
    setTimeout(function () { $("adminPinInput").focus(); }, 60);
  }

  function tryAdminLogin() {
    api("/api/admin/login", "POST", { pin: $("adminPinInput").value })
      .then(function () {
        isAdmin = true;
        $("adminOverlay").classList.add("hidden");
        $("adminPinInput").value = "";
        renderPregacoes();
        if (adminReturnView === "home") {
          loadPregacoes();
          setView("home");
        } else {
          loadAdvanced();
          setView("advanced");
        }
      }).catch(function () {
        $("adminPinError").classList.remove("hidden");
        $("adminPinInput").select();
      });
  }

  function openAdvanced() {
    if (isAdmin) { loadAdvanced(); setView("advanced"); }
    else openAdmin();
  }

  function showSetup() {
    wizStep = 1;
    $("setupOverlay").classList.remove("hidden");
    api("/api/setup").then(function (info) {
      $("wizAdminBlock").classList.toggle("hidden", !!info.admin);
      $("wizDir").value = info.recordings_dir || "";
      $("wizDriveStatus").textContent = info.drive_connected
        ? "Conta ja conectada" : "nao conectada";
      var st = (status || {}).storage || {};
      $("wizFree").textContent = "Espaco livre: " +
        (st.ok ? bytes(st.free_mb * 1024 * 1024) : "--");
      return api("/api/audio/devices");
    }).then(function (devs) {
      fillSelect($("wizDevice"),
        [{ value: "auto", label: "AUTO (detectar interface USB)" }].concat(
          (devs.items || []).map(function (d) {
            return { value: d.hw, label: d.hw + " - " + d.name };
          })), devs.selected && devs.selected.hw);
      var sel = $("wizDevice");
      var cur = sel.options[sel.selectedIndex];
      $("wizDeviceHint").textContent = cur && cur.value !== "auto"
        ? "selecionado: " + cur.label : "conecte a interface USB e clique em AVANCAR";
    }).catch(function () {});
    renderWiz();
  }

  function renderWiz() {
    [1, 2, 3, 4].forEach(function (n) {
      $("wizStep" + n).classList.toggle("hidden", wizStep !== n);
    });
    document.querySelectorAll("#setupSteps .stepdot").forEach(function (dot) {
      dot.classList.toggle("active", Number(dot.dataset.dot) <= wizStep);
    });
    $("wizBack").disabled = wizStep === 1;
    $("wizNext").classList.toggle("hidden", wizStep === 4);
    $("wizFinish").classList.toggle("hidden", wizStep !== 4);
    if (wizStep === 4) {
      var sel = $("wizDevice");
      var cur = sel.options[sel.selectedIndex];
      $("wizSumAudio").textContent = cur ? cur.label : "--";
      $("wizSumDir").textContent = $("wizDir").value || "--";
      $("wizSumDrive").textContent = $("wizDriveStatus").textContent;
    }
  }

  function wizAdvance() {
    if (wizStep === 1) {
      api("/api/config", "POST", { "audio.device": $("wizDevice").value })
        .then(function () { wizStep = 2; renderWiz(); })
        .catch(function (e) { toast(e.message, "error"); openWizAdmin(); });
    } else if (wizStep === 2) {
      api("/api/config", "POST", { "storage.recordings_dir": $("wizDir").value })
        .then(function () { wizStep = 3; renderWiz(); })
        .catch(function (e) { toast(e.message, "error"); openWizAdmin(); });
    } else {
      wizStep = 4;
      renderWiz();
    }
  }

  function openWizAdmin() {
    $("wizAdminBlock").classList.remove("hidden");
    $("wizAdminError").classList.add("hidden");
    setTimeout(function () { $("wizAdminPin").focus(); }, 60);
  }

  function tryWizAdmin() {
    api("/api/admin/login", "POST", { pin: $("wizAdminPin").value })
      .then(function () {
        isAdmin = true;
        $("wizAdminPin").value = "";
        $("wizAdminBlock").classList.add("hidden");
        $("wizAdminError").classList.add("hidden");
        toast("Configuracoes liberadas", "success");
      }).catch(function () {
        $("wizAdminError").classList.remove("hidden");
        $("wizAdminPin").select();
      });
  }

  function finishSetup() {
    api("/api/setup/complete", "POST").then(function () {
      $("setupOverlay").classList.add("hidden");
      toast("Configuracao inicial concluida!", "success");
      addNotif("Configuracao inicial concluida", "success");
      loadConfig();
    }).catch(function (e) { toast(e.message, "error"); });
  }

  // ---------------------------------------------------------------- eventos
  function bind() {
    $("pinBtn").addEventListener("click", tryLogin);
    $("pinInput").addEventListener("keydown", function (e) {
      if (e.key === "Enter") tryLogin();
    });

    $("btnStart").addEventListener("click", doStart);
    $("btnStop").addEventListener("click", askStop);
    $("confirmCancel").addEventListener("click", function () {
      $("confirmOverlay").classList.add("hidden");
      refresh();
    });
    $("confirmOk").addEventListener("click", doStop);

    $("navHome").addEventListener("click", function () { setView("home"); });
    $("navConfig").addEventListener("click", function () {
      setView("config");
      if (authed) loadConfig();
    });
    $("navHistory").addEventListener("click", function () {
      setView("history");
      if (authed) loadHistory();
    });

    $("configForm").addEventListener("submit", saveConfig);
    $("advancedForm").addEventListener("submit", saveAdvanced);
    $("btnAdvanced").addEventListener("click", openAdvanced);
    $("btnRemoteToken").addEventListener("click", toggleRemoteToken);
    $("btnRemoteSave").addEventListener("click", saveRemoteConfig);
    $("btnConfigAudioTest").addEventListener("click", function () {
      var form = $("advancedForm");
      testSelectedAudio("cfgAudioTestResult", "btnConfigAudioTest", {
        device: $("cfgDevice").value,
        sample_rate: form.elements["audio.sample_rate"].value,
        channels: form.elements["audio.channels"].value
      });
    });
    $("btnAdvancedBack").addEventListener("click", function () {
      setView("config");
      loadConfig();
    });
    $("adminOk").addEventListener("click", tryAdminLogin);
    $("adminCancel").addEventListener("click", function () {
      $("adminOverlay").classList.add("hidden");
    });
    $("adminPinInput").addEventListener("keydown", function (e) {
      if (e.key === "Enter") tryAdminLogin();
    });
    $("btnLoadLogs").addEventListener("click", function () {
      $("logsBox").textContent = "carregando...";
      api("/api/logs?lines=150").then(function (r) {
        $("logsBox").textContent = r.content || "(log vazio)";
      }).catch(function (e) { $("logsBox").textContent = e.message; });
    });
    $("btnDriveTestFolder").addEventListener("click", function () {
      api("/api/drive/test", "POST").then(function (r) {
        toast("Pasta acessivel (id " + r.folder_id + ")", "success");
      }).catch(function (e) { toast(e.message, "error"); });
    });

    // assistente de primeiro acesso
    $("wizNext").addEventListener("click", wizAdvance);
    $("wizBack").addEventListener("click", function () {
      if (wizStep > 1) { wizStep--; renderWiz(); }
    });
    $("wizFinish").addEventListener("click", finishSetup);
    $("wizAdminOk").addEventListener("click", tryWizAdmin);
    $("wizAdminPin").addEventListener("keydown", function (e) {
      if (e.key === "Enter") tryWizAdmin();
    });
    $("wizAudioTest").addEventListener("click", function () {
      testSelectedAudio("wizAudioResult", "wizAudioTest", {device: $("wizDevice").value});
    });
    $("wizDriveConnect").addEventListener("click", function () {
      api("/api/drive/connect", "POST").then(function (r) {
        if (r.url) window.location.assign(r.url);
      }).catch(function (e) { toast(e.message, "error"); });
    });

    $("btnAudioTest").addEventListener("click", function () {
      var el = $("audioTestResult");
      el.textContent = "testando (2s)...";
      api("/api/audio/test", "POST").then(function (r) {
        if (!r.ok) { el.textContent = "FALHA: " + r.error; return; }
        el.textContent = r.silent
          ? "SILENCIO - suba o fader da mesa"
          : "Sinal OK · pico " + r.peak_db + " dBFS";
      }).catch(function (e) { el.textContent = e.message; });
    });

    $("btnRetryUploads").addEventListener("click", function () {
      api("/api/uploads/retry", "POST").then(function (r) {
        toast(r.requeued + " upload(s) na fila", "success");
      }).catch(function (e) { toast(e.message, "error"); });
    });

    $("btnDriveConnect").addEventListener("click", function () {
      // fluxo oficial do Google, na MESMA aba; sem credenciais o servidor
      // responde 412 e a interface apenas orienta o usuario comum.
      api("/api/drive/connect", "POST").then(function (r) {
        if (r.url) window.location.assign(r.url);
      }).catch(function (e) {
        toast(e.message, "error");
        if (e.data && e.data.error === "drive_nao_configurado" && isAdmin) {
          loadAdvanced();
          setView("advanced");
        }
      });
    });
    $("btnDriveDisconnect").addEventListener("click", function () {
      api("/api/drive/disconnect", "POST").then(function () {
        toast("Conta desconectada", "warning");
        loadConfig();
      }).catch(function (e) { toast(e.message, "error"); });
    });
    $("btnDriveTest").addEventListener("click", function () {
      api("/api/drive/test", "POST").then(function (r) {
        toast("Conexao OK - pasta acessivel", "success");
      }).catch(function (e) { toast(e.message, "error"); });
    });

    // PREGACOES (S4)
    $("btnAddPregacao").addEventListener("click", function () { openPregacaoModal(null); });
    $("btnScheduleAdmin").addEventListener("click", function () { openAdmin("home"); });
    $("pregacaoForm").addEventListener("submit", savePregacao);
    $("pregacaoCancel").addEventListener("click", closePregacaoModal);
    $("btnImportPregacao").addEventListener("click", openImportModal);
    $("importCancel").addEventListener("click", closeImportModal);
    $("importFile").addEventListener("change", previewImport);
    $("importConfirm").addEventListener("click", confirmImport);
    $("btnDownloadModelo").addEventListener("click", function (ev) {
      ev.preventDefault();
      downloadModelo();
    });

    $("btnNlmCheck").addEventListener("click", function () {
      if (nlmDiagnostico || nlmLoginPedido || this.disabled) return;
      nlmDiagnostico = true;
      pintaNlm(nlmUltimo);
      api("/api/estudos/diagnosticar", "POST").then(function (r) {
        nlmDiagnostico = false;
        pintaNlm(r);
        if (r.login && r.login.em_andamento) {
          toast("Conclua o login no navegador do PC e aguarde a confirmacao.", "info");
        } else if (r.renovada) {
          toast("Sessao renovada automaticamente", "success");
        } else if (r.retomados) {
          toast(r.retomados + " estudo(s) retomado(s)", "success");
        } else if (r.estado === "ok") {
          toast("Sessao do NotebookLM ativa", "success");
        } else {
          toast("Sessao " + (r.estado || "?") + " - " + (r.detalhe || ""),
            "error");
        }
      }).catch(function (e) {
        nlmDiagnostico = false;
        pintaNlm(nlmUltimo);
        toast(e.message, "error");
      });
    });
    $("btnNlmLogin").addEventListener("click", function () {
      if (nlmLoginPedido || nlmDiagnostico || this.disabled) return;
      nlmLoginPedido = true;
      pintaNlm(nlmUltimo);
      api("/api/estudos/reconectar", "POST").then(function (r) {
        nlmLoginPedido = false;
        pintaNlm(Object.assign({}, nlmUltimo || {}, { login: r.login || {} }));
        toast(r.lancado === false
          ? "Login ja em andamento. Conclua no navegador do PC."
          : "Abrindo login no PC. Entre na sua conta e aguarde a confirmacao.", "info");
      }).catch(function (e) {
        nlmLoginPedido = false;
        pintaNlm(Object.assign({}, nlmUltimo || {}, {
          login: { em_andamento: false, estado: "erro", detalhe: e.message }
        }));
        toast(e.message, "error");
      });
    });
  }

  function setView(view) {
    if (view !== "advanced") renderRemotePairing(null);
    document.body.dataset.view = view;
    $("viewHome").classList.toggle("hidden", view !== "home");
    $("viewConfig").classList.toggle("hidden", view !== "config");
    $("viewAdvanced").classList.toggle("hidden", view !== "advanced");
    $("viewHistory").classList.toggle("hidden", view !== "history");
    $("navHome").classList.toggle("active", view === "home");
    $("navHistory").classList.toggle("active", view === "history");
    $("navConfig").classList.toggle("active", view === "config" || view === "advanced");
    history.replaceState(null, "",
      view === "home" ? "/" : (view === "history" ? "/historico" : "/config"));
  }

  // ---------------------------------------------------------------- boot
  function boot() {
    bind();
    // resultado do login do Google (retornado em /config?drive=ok|erro)
    var q = new URLSearchParams(location.search);
    var driveRes = q.get("drive");
    if (location.pathname.indexOf("/config") === 0) setView("config");
    else if (location.pathname.indexOf("/historico") === 0) setView("history");
    if (driveRes) {
      history.replaceState(null, "", "/config");
      var dmsg = q.get("msg") || "";
      if (driveRes === "ok") toast("Conta Google conectada ao Drive", "success");
      else toast("Falha ao conectar o Drive: " + dmsg, "error");
    }

    // o estado geral (PRONTO/GRAVANDO/espaco/rede) e publico: ja exibe atras do
    // login para quem olha a tela, mesmo sem ter digitado o PIN.
    refresh();
    setInterval(refresh, 15000);

    api("/api/me").then(function (me) {
      authed = me.auth;
      pinRequired = me.pin_required;
      isAdmin = !!me.admin;
      $("deviceName").textContent = me.device_name;
      if (pinRequired && !authed) { showLogin(true); return; }
      start();
      if (authed && me.setup_needed) showSetup();
    }).catch(function () { showLogin(true); });
  }

  function start() {
    refresh().then(function () {
      if (authed) loadConfig();
      if (authed) loadPregacoes();
      if (authed && document.body.dataset.view === "history") loadHistory();
      // historico de notificacoes
      if (authed) {
        api("/api/events/history").then(function (data) {
          (data.items || []).slice().reverse().forEach(function (item) {
            addNotif(item.message, item.level, item.ts);
          });
        }).catch(function () {});
      }
      connect();
    });
  }

  document.addEventListener("DOMContentLoaded", boot);
  window.__pregacao = {
    reconnect: function () { if (authed) start(); }
  };
})();
