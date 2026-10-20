#!/usr/bin/env node
/**
 * send.js — envia um arquivo (PDF) por WhatsApp usando Baileys (WhatsApp Web nao-oficial).
 *
 * Uso:
 *   node whatsapp/send.js <numero-com-DDI> <arquivo> [legenda]
 *   node whatsapp/send.js 5511999999999 ../output/estudo.pdf "Estudo devocional"
 *   node whatsapp/send.js --login   (apenas conectar / gerar QR)
 *
 * Primeira execucao: gera whatsapp/qr.png (abre automaticamente) — leia com o
 * WhatsApp (Aparelhos conectados > Conectar aparelho). A sessao fica em whatsapp/auth/.
 */

const fs = require("fs");
const path = require("path");
const { makeWASocket, useMultiFileAuthState, Browsers, DisconnectReason } = require("baileys");
const qrcode = require("qrcode-terminal");
const pino = require("pino");

// O pacote usa pasta gravavel por usuario. Nunca distribuir auth/ ou QRs.
const dataRoot = process.env.PREGACAO_PIPELINE_HOME
  ? path.resolve(process.env.PREGACAO_PIPELINE_HOME)
  : path.resolve(__dirname, "..");
const whatsappDir = path.join(dataRoot, "whatsapp");

function fail(msg) {
  console.error("ERRO: " + msg);
  process.exit(1);
}

async function main() {
  const args = process.argv.slice(2);
  const loginOnly = args[0] === "--login";
  const statusOnly = args[0] === "--status";
  const noOpen = args.includes("--no-open");
  const [phoneRaw, filePath, ...captionParts] = loginOnly || statusOnly ? [] : args;
  if (!loginOnly && !statusOnly && (!phoneRaw || !filePath)) {
    console.error("Uso: node send.js <numero com DDI> <arquivo> [legenda]");
    console.error("     node send.js --login   (apenas conectar/QR)");
    process.exit(2);
  }
  const phone = phoneRaw ? phoneRaw.replace(/\D/g, "") : "";
  if (!loginOnly && !statusOnly && phone.length < 10) fail("numero invalido (use DDI+DDD+numero, ex.: 5511999999999)");
  const abs = filePath ? path.resolve(filePath) : "";
  if (!loginOnly && !statusOnly && !fs.existsSync(abs)) fail("arquivo nao encontrado: " + abs);

  const caption = captionParts.join(" ");
  const fileName = filePath ? path.basename(abs) : "";
  const ext = path.extname(fileName).toLowerCase();
  const mimetypes = {
    ".pdf": "application/pdf",
    ".md": "text/markdown",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".jpg": "image/jpeg",
    ".png": "image/png",
  };
  const mimetype = mimetypes[ext] || "application/octet-stream";
  const buffer = filePath ? fs.readFileSync(abs) : null;
  const jid = `${phone}@s.whatsapp.net`;

  fs.mkdirSync(whatsappDir, { recursive: true });
  if (!loginOnly && !fs.existsSync(path.join(whatsappDir, "auth", "creds.json"))) {
    fail("sessao do WhatsApp ausente; conecte pelo QR em CONFIG");
  }
  const { state, saveCreds } = await useMultiFileAuthState(path.join(whatsappDir, "auth"));

  let generation = 0;
  let attempts = 0;
  let settled = false;
  const done = (code) => {
    if (settled) return;
    settled = true;
    setTimeout(() => process.exit(code), 500);
  };

  const start = () => {
    const myGen = ++generation;
    const sock = makeWASocket({
      auth: state,
      browser: Browsers.ubuntu("Chrome"),
      printQRInTerminal: false,
      logger: pino({ level: "silent" }),
    });
    sock.ev.on("creds.update", saveCreds);
    sock.ev.on("connection.update", (update) => handleUpdate(update, myGen, sock));
  };

  const handleUpdate = async (update, myGen, sock) => {
    if (myGen !== generation || settled) return; // socket antigo — ignora
    const { connection, lastDisconnect, qr } = update;

    if (qr) {
      if (!loginOnly) fail("sessao do WhatsApp exige novo login; conecte pelo QR em CONFIG");
      try {
        const QRCode = require("qrcode");
        const stale = path.join(whatsappDir, "qr.png");
        try {
          fs.unlinkSync(stale);
        } catch (_) {
          /* pode nao existir ou estar aberto */
        }
        const pngPath = path.join(whatsappDir, `qr_${Date.now()}.png`);
        await QRCode.toFile(pngPath, qr, { width: 640, margin: 2, errorCorrectionLevel: "M" });
        if (loginOnly && !noOpen) {
          // pareamento manual (--login): abre a imagem para o usuario escanear
          console.log("QR gerado: " + pngPath + " — abrindo a imagem...");
          require("child_process").exec(`start "" "${pngPath}"`);
        } else if (!loginOnly) {
          // envio automatico: loga o caminho sem abrir janela nenhuma
          console.log("QR gerado (sem abrir janela): " + pngPath);
        }
      } catch (err) {
        console.error("Falha ao gerar PNG do QR: " + err.message);
      }
      if (!noOpen) {
        console.log("QR (texto, caso a imagem nao abra):");
        qrcode.generate(qr, { small: true });
      }
    }

    if (connection === "open") {
      if (statusOnly) {
        console.log("OK: conexao WhatsApp verificada");
        done(0);
        return;
      }
      if (loginOnly) {
        console.log("OK: WhatsApp conectado. Sessao salva em whatsapp/auth/.");
        done(0);
        return;
      }
      try {
        const message = await sock.sendMessage(jid, {
          document: buffer,
          fileName,
          mimetype,
          caption: caption || undefined,
        });
        if (!message || !message.key || !message.key.id) {
          throw new Error("WhatsApp nao retornou ID da mensagem");
        }
        console.log(`ACEITO:${message.key.id}`);
        console.log(`OK: arquivo aceito pelo servidor para +${phone} (${fileName}); entrega ao destinatario nao confirmada`);
        done(0);
      } catch (err) {
        console.error("ERRO ao enviar: " + (err && err.message ? err.message : err));
        done(1);
      }
    }

    if (connection === "close") {
      const code =
        lastDisconnect && lastDisconnect.error && lastDisconnect.error.output
          ? lastDisconnect.error.output.statusCode
          : undefined;
      if (code === DisconnectReason.loggedOut) {
        fail("sessao do WhatsApp encerrada — apague a pasta whatsapp/auth e leia o QR novamente");
      }
      if (attempts >= 4) {
        fail("conexao falhou apos 4 tentativas (codigo " + code + ")");
      }
      attempts += 1;
      console.log(`conexao fechada (codigo ${code}) — reconectando (${attempts}/4)...`);
      setTimeout(start, 1500);
    }
  };

  start();
}

main().catch((err) => fail(err && err.stack ? err.stack : String(err)));
