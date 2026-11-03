package com.diomaster2d.grokbot

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.util.concurrent.TimeUnit

class MainActivity : ComponentActivity() {
 override fun onCreate(savedInstanceState: Bundle?) { super.onCreate(savedInstanceState); setContent { MaterialTheme { App() } } }
}
data class DeskTool(val name: String, val description: String)

class DeskClient(private val base: String, private val seat: String, private val token: String) {
 private val http = OkHttpClient.Builder().connectTimeout(15, TimeUnit.SECONDS).readTimeout(45, TimeUnit.SECONDS).build()
 private val media = "application/json".toMediaType()
 private var id = 0
 private suspend fun rpc(method: String, params: JSONObject = JSONObject(), notification: Boolean = false): JSONObject = withContext(Dispatchers.IO) {
  val n = ++id
  val body = JSONObject().put("jsonrpc","2.0").put("method",method).put("params",params)
  if (!notification) body.put("id",n)
  val req = Request.Builder().url("$base/mcp/$seat").header("Authorization","Bearer $token").post(body.toString().toRequestBody(media)).build()
  http.newCall(req).execute().use { res ->
   val text = res.body?.string().orEmpty()
   check(res.isSuccessful) { "HTTP ${res.code}: ${text.take(400)}" }
   if (notification) JSONObject() else JSONObject(text).also { check(!it.has("error")) { it.optJSONObject("error").toString() } }
  }
 }
 suspend fun connect(): List<DeskTool> {
  rpc("initialize", JSONObject().put("protocolVersion","2024-11-05").put("capabilities",JSONObject()).put("clientInfo",JSONObject().put("name","DioMasteR2D-Android").put("version","0.1.0")))
  rpc("notifications/initialized", notification=true)
  val a = rpc("tools/list").optJSONObject("result")?.optJSONArray("tools")
  return if (a == null) emptyList() else (0 until a.length()).mapNotNull { i -> a.optJSONObject(i)?.let { DeskTool(it.optString("name"),it.optString("description")) } }
 }
 suspend fun call(name: String, args: JSONObject): String = rpc("tools/call",JSONObject().put("name",name).put("arguments",args)).toString(2)
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable fun App() {
 var url by remember { mutableStateOf("https://") }; var seat by remember { mutableStateOf("scout") }; var token by remember { mutableStateOf("") }
 var tools by remember { mutableStateOf(emptyList<DeskTool>()) }; var chosen by remember { mutableStateOf<DeskTool?>(null) }
 var args by remember { mutableStateOf("{}") }; var result by remember { mutableStateOf("Σύνδεσε το PumpGrok Desk Gateway.") }
 var busy by remember { mutableStateOf(false) }; var connected by remember { mutableStateOf(false) }; var client by remember { mutableStateOf<DeskClient?>(null) }
 val scope = rememberCoroutineScope()
 fun task(block: suspend () -> Unit) { scope.launch { busy=true; try { block() } catch(e: Exception) { result="Σφάλμα: ${e.message}"; connected=false } finally { busy=false } } }
 Scaffold(topBar={ TopAppBar(title={ Text("DioMasteR2D Grokbot") }) }) { pad ->
  LazyColumn(Modifier.fillMaxSize().padding(pad).padding(16.dp), verticalArrangement=Arrangement.spacedBy(10.dp)) {
   item {
    Text("PUMPGROK ANDROID COMPANION", style=MaterialTheme.typography.labelLarge)
    Text("PAPER TRADING ONLY — δεν εκτελεί πραγματικές συναλλαγές.", color=MaterialTheme.colorScheme.error)
    OutlinedTextField(url,{url=it.trim()},label={Text("Gateway HTTPS URL")},modifier=Modifier.fillMaxWidth(),singleLine=true)
    OutlinedTextField(seat,{seat=it.trim().lowercase()},label={Text("Seat: scout, risk, whale κ.λπ.")},modifier=Modifier.fillMaxWidth(),singleLine=true)
    OutlinedTextField(token,{token=it},label={Text("Bearer token")},visualTransformation=PasswordVisualTransformation(),modifier=Modifier.fillMaxWidth(),singleLine=true)
    Button(enabled=!busy && token.isNotBlank() && url.startsWith("https://"),onClick={ task {
     require(url.startsWith("https://")) { "Χρειάζεται HTTPS" }
     val c=DeskClient(url.removeSuffix("/"),seat,token); val found=c.connect(); client=c; tools=found; connected=true; result="Συνδέθηκε. Βρέθηκαν ${found.size} εργαλεία."
    } }) { Text(if(busy) "Σύνδεση..." else "Σύνδεση") }
    Text(if(connected) "Συνδεδεμένο" else "Αποσυνδεδεμένο")
   }
   item { HorizontalDivider(); Text("Εργαλεία",style=MaterialTheme.typography.titleMedium) }
   items(tools) { t -> Card(Modifier.fillMaxWidth().clickable { chosen=t; result=t.description }) { Column(Modifier.padding(12.dp)) { Text(t.name); Text(t.description,style=MaterialTheme.typography.bodySmall) } } }
   chosen?.let { t -> item {
    Text("Εργαλείο: ${t.name}",style=MaterialTheme.typography.titleMedium)
    OutlinedTextField(args,{args=it},label={Text("Arguments JSON")},modifier=Modifier.fillMaxWidth(),minLines=3)
    Button(enabled=connected && !busy,onClick={task { result=client!!.call(t.name,JSONObject(args)) }}) { Text("Εκτέλεση") }
   } }
   item { HorizontalDivider(); Text("Αποτέλεσμα",style=MaterialTheme.typography.titleMedium); Text(result,style=MaterialTheme.typography.bodySmall)
    TextButton(onClick={token="";client=null;connected=false;tools=emptyList();chosen=null;result="Αποσυνδέθηκε."}) { Text("Αποσύνδεση / καθαρισμός token") }
   }
  }
 }
}
