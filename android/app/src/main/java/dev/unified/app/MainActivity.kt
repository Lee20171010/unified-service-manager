package dev.unified.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.graphics.Color
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.repeatOnLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Diagnostics.record(DiagnosticEvent.ACTIVITY_CREATE)
        enableEdgeToEdge()
        val credentials = Credentials(applicationContext)
        val appearance = ThemePreferences(applicationContext)
        setContent {
            var themeMode by remember { mutableStateOf(appearance.read()) }
            val dark = themeMode.isDark(isSystemInDarkTheme())
            SideEffect {
                val transparent = android.graphics.Color.TRANSPARENT
                enableEdgeToEdge(
                    statusBarStyle =
                        if (dark) SystemBarStyle.dark(transparent)
                        else SystemBarStyle.light(transparent, transparent),
                    navigationBarStyle =
                        if (dark) SystemBarStyle.dark(transparent)
                        else SystemBarStyle.light(transparent, transparent),
                )
            }
            UnifiedTheme(mode = themeMode) {
                val vm: MainViewModel =
                    viewModel(
                        factory =
                            object : ViewModelProvider.Factory {
                                @Suppress("UNCHECKED_CAST")
                                override fun <T : ViewModel> create(modelClass: Class<T>): T =
                                    MainViewModel(credentials) as T
                            }
                    )
                AppRoute(vm, themeMode) { mode ->
                    appearance.write(mode)
                    themeMode = mode
                }
            }
        }
    }

    override fun onStart() {
        super.onStart()
        Diagnostics.record(DiagnosticEvent.ACTIVITY_START)
    }

    override fun onStop() {
        Diagnostics.record(DiagnosticEvent.ACTIVITY_STOP)
        super.onStop()
    }
}

@Composable
internal fun AppRoute(vm: MainViewModel, themeMode: ThemeMode, onThemeChange: (ThemeMode) -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    var diagnosticsOpen by rememberSaveable { mutableStateOf(false) }
    if (diagnosticsOpen) DiagnosticsDialog(dismiss = { diagnosticsOpen = false })
    val lifecycle = LocalLifecycleOwner.current
    LaunchedEffect(vm, lifecycle) {
        lifecycle.lifecycle.repeatOnLifecycle(Lifecycle.State.STARTED) { vm.observe() }
    }
    key(vm.connection.first) {
        UnifiedScreen(
            state,
            vm.connection,
            vm::connect,
            vm::mutate,
            vm::showJob,
            vm::openTerminal,
            vm::dismissError,
            themeMode,
            onThemeChange,
            vm::pluginDocument,
            onDiagnostics = { diagnosticsOpen = true },
        )
    }
    state.job?.let { job ->
        JobConsole(
            job,
            state.logs,
            vm::closeJob,
            vm::fullLog,
            state.session,
            state.inputBusy,
            { text, close -> vm.jobInput(text, close) },
        )
    }
    state.terminalHost?.let { host ->
        TerminalDialog(host, state.terminalOutput, vm::terminalInput, vm::closeTerminal)
    }
}
