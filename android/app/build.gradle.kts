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
        // 1.1 = PINs de volta (170414) e botao sem travar em ERROR/COMPLETED.
        // 1.2 = tela de redes Wi-Fi do EQUIPAMENTO (WIFI_SCAN/WIFI_CONNECT).
        // 1.3 = tela de ONDE GRAVAR (SSD x cartao SD), tela de conta Google
        //       (conector loopback) e menu sempre visivel.
        // 1.4 = o encaixe das barras do sistema, agora consumindo os insets -
        //       na 1.3 a action bar continuava por cima do conteudo.
        // O operador confere esta string na barra superior.
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
