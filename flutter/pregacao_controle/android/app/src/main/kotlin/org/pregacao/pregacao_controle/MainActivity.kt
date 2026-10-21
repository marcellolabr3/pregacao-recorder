package org.pregacao.pregacao_controle

import android.app.Activity
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import android.os.Build
import android.content.pm.ShortcutInfo
import android.content.pm.ShortcutManager
import android.graphics.drawable.Icon
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.util.UUID

class MainActivity : FlutterActivity() {
    private val imageRequest = 6107
    private var pendingResult: MethodChannel.Result? = null
    private var pendingKind: String? = null

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger,
            "org.pregacao.pregacao_controle/appearance").setMethodCallHandler { call, result ->
            if (call.method == "createShortcut") {
                try {
                    result.success(createShortcut(call.argument<String>("path")))
                } catch (error: Exception) {
                    result.error("shortcut_failed", error.message ?: "Atalho indisponivel", null)
                }
                return@setMethodCallHandler
            }
            if (call.method != "chooseImage") {
                result.notImplemented()
                return@setMethodCallHandler
            }
            val kind = call.argument<String>("kind")
            if (kind != "logo" && kind != "background") {
                result.error("invalid_kind", "Tipo de imagem invalido", null)
                return@setMethodCallHandler
            }
            if (pendingResult != null) {
                result.error("busy", "Ja existe uma escolha de imagem em andamento", null)
                return@setMethodCallHandler
            }
            pendingResult = result
            pendingKind = kind
            val intent = Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
                addCategory(Intent.CATEGORY_OPENABLE)
                type = "image/*"
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }
            try {
                startActivityForResult(intent, imageRequest)
            } catch (error: Exception) {
                pendingResult = null
                pendingKind = null
                result.error("picker_failed", "Nao foi possivel abrir as imagens", null)
            }
        }
    }

    @Deprecated("A API de selecao do Android ainda devolve o resultado aqui")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode != imageRequest) return
        val result = pendingResult ?: return
        val kind = pendingKind ?: return
        pendingResult = null
        pendingKind = null
        val uri = data?.data
        if (resultCode != Activity.RESULT_OK || uri == null) {
            result.success(null)
            return
        }
        try {
            result.success(copyImage(uri, kind))
        } catch (error: Exception) {
            result.error("invalid_image", error.message ?: "Imagem invalida", null)
        }
    }

    private fun copyImage(uri: Uri, kind: String): String {
        val stream = contentResolver.openInputStream(uri)
            ?: throw IOException("Nao foi possivel ler a imagem")
        val buffer = ByteArrayOutputStream()
        stream.use { input ->
            val chunk = ByteArray(8192)
            while (true) {
                val size = input.read(chunk)
                if (size < 0) break
                buffer.write(chunk, 0, size)
                if (buffer.size() > 5 * 1024 * 1024) {
                    throw IOException("Escolha uma imagem de ate 5 MB")
                }
            }
        }
        val bytes = buffer.toByteArray()
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeByteArray(bytes, 0, bytes.size, bounds)
        if (bounds.outWidth <= 0 || bounds.outHeight <= 0) {
            throw IOException("Formato de imagem nao reconhecido")
        }
        val maximum = if (kind == "logo") 512 else 1600
        var sample = 1
        while (maxOf(bounds.outWidth, bounds.outHeight) / sample > maximum) {
            sample *= 2
        }
        val options = BitmapFactory.Options().apply { inSampleSize = sample }
        val bitmap = BitmapFactory.decodeByteArray(bytes, 0, bytes.size, options)
            ?: throw IOException("Nao foi possivel abrir a imagem")
        val directory = File(filesDir, "appearance")
        if (!directory.exists() && !directory.mkdirs()) {
            bitmap.recycle()
            throw IOException("Nao foi possivel salvar a imagem")
        }
        val base = "$kind-${UUID.randomUUID()}"
        val temporary = File(directory, "$base.tmp")
        val target = File(directory, "$base.${if (kind == "logo") "png" else "jpg"}")
        try {
            FileOutputStream(temporary).use { output ->
                val format = if (kind == "logo") Bitmap.CompressFormat.PNG else Bitmap.CompressFormat.JPEG
                if (!bitmap.compress(format, 88, output)) {
                    throw IOException("Nao foi possivel converter a imagem")
                }
            }
            if (!temporary.renameTo(target)) throw IOException("Nao foi possivel salvar a imagem")
            return target.absolutePath
        } finally {
            bitmap.recycle()
            temporary.delete()
        }
    }

    private fun createShortcut(path: String?): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) {
            throw IOException("Atalho personalizado requer Android 8 ou superior")
        }
        val manager = getSystemService(ShortcutManager::class.java)
            ?: throw IOException("Atalhos nao disponiveis neste aparelho")
        if (!manager.isRequestPinShortcutSupported) {
            throw IOException("A tela inicial nao aceita atalhos personalizados")
        }
        val directory = File(filesDir, "appearance").canonicalFile
        val image = if (path.isNullOrBlank()) null else File(path).canonicalFile
        if (image == null || image.parentFile != directory ||
            !image.name.startsWith("logo-") || image.extension != "png") {
            throw IOException("Escolha primeiro uma imagem para o icone")
        }
        val bitmap = BitmapFactory.decodeFile(image.absolutePath)
            ?: throw IOException("Escolha primeiro uma imagem para o icone")
        try {
            val launch = Intent(this, MainActivity::class.java).apply {
                action = Intent.ACTION_MAIN
                addCategory(Intent.CATEGORY_LAUNCHER)
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            }
            val shortcut = ShortcutInfo.Builder(this, "pregacao-custom")
                .setShortLabel("Pregacao Controle")
                .setIcon(Icon.createWithBitmap(bitmap))
                .setIntent(launch)
                .build()
            return manager.requestPinShortcut(shortcut, null)
        } finally {
            bitmap.recycle()
        }
    }
}
