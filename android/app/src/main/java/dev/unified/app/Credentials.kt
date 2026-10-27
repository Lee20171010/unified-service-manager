package dev.unified.app

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/** Token encrypted by a non-exportable Android Keystore key; excluded from backup. */
interface ConnectionStore {
    fun hasSavedConnection(): Boolean

    fun read(): Pair<String, String>

    fun save(base: String, token: String)
}

class Credentials(context: Context) : ConnectionStore {
    private val preferences = context.getSharedPreferences("connection", Context.MODE_PRIVATE)

    private fun key(): SecretKey {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (store.getKey("unified-token", null) as? SecretKey)?.let {
            return it
        }
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
            .apply {
                init(
                    KeyGenParameterSpec.Builder(
                            "unified-token",
                            KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT,
                        )
                        .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                        .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                        .build()
                )
            }
            .generateKey()
    }

    override fun hasSavedConnection(): Boolean = preferences.contains("base")

    override fun read(): Pair<String, String> {
        val base = preferences.getString("base", "").orEmpty()
        val saved =
            preferences.getString("token", null) ?: return base to ""
        return try {
            val bytes = Base64.decode(saved, Base64.NO_WRAP)
            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, bytes.copyOfRange(0, 12)))
            base to String(cipher.doFinal(bytes.copyOfRange(12, bytes.size)), Charsets.UTF_8)
        } catch (_: Exception) {
            base to ""
        }
    }

    override fun save(base: String, token: String) {
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, key())
        val value =
            Base64.encodeToString(
                cipher.iv + cipher.doFinal(token.toByteArray(Charsets.UTF_8)),
                Base64.NO_WRAP,
            )
        preferences.edit().putString("base", base).putString("token", value).apply()
    }
}
