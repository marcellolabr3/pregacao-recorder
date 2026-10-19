plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "org.pregacao.controle"
    compileSdk = 35

    defaultConfig {
        applicationId = "org.pregacao.controle"
        minSdk = 26
        targetSdk = 35
        versionCode = 5
        // Fonte legada; distribuicao atual usa o projeto Flutter.
        versionName = "1.4"
    }

    buildTypes {
        release {
            // sem assinatura propria: o APK de teste e o debug
            isMinifyEnabled = false
            isShrinkResources = false
        }
    }

    buildFeatures {
        // o AGP 8 nao gera BuildConfig por padrao; precisamos dele para
        // mostrar o versionName na tela do operador
        buildConfig = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    // mesmo cliente MQTT do equipamento (o agente usa a mesma familia)
    implementation("org.eclipse.paho:org.eclipse.paho.client.mqttv3:1.2.5")
}
