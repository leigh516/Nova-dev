package kr.nova.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent

/** Android: 에뮬레이터에서 호스트의 게이트웨이는 10.0.2.2 */
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { App(apiBase = "http://10.0.2.2:8080/v1") }
    }
}
