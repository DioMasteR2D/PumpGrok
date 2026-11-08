package com.diomaster2d.grokbot

import android.os.Bundle
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.ui.unit.IntOffset
import kotlin.math.cos
import kotlin.math.sin
import kotlinx.coroutines.delay
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.util.concurrent.TimeUnit

private val Bg = Color(0xFF08090D)
private val Panel = Color(0xFF151820)
private val Red = Color(0xFF9B5CFF)
private val Blue = Color(0xFF16C8FF)
private val Purple = Color(0xFF6C4DFF)
private val Green = Color(0xFF20D889)
private val Muted = Color(0xFF9299A8)

class MainActivity : ComponentActivity() {
 override fun onCreate(savedInstanceState: Bundle?) { super.onCreate(savedInstanceState); setContent { GrokTheme { App() } } }
}
@Composable private fun GrokTheme(content: @Composable () -> Unit) {
 MaterialTheme(colorScheme = darkColorScheme(primary=Red, background=Bg, surface=Panel, onBackground=Color.White, onSurface=Color.White), content=content)
}
data class DeskTool(val name:String,val description:String,val schema:JSONObject)
class DeskClient(private val base:String,private val seat:String,private val token:String) {
 private val http=OkHttpClient.Builder().connectTimeout(15,TimeUnit.SECONDS).readTimeout(45,TimeUnit.SECONDS).build()
 private val media="application/json".toMediaType()
 private var id=0
 private suspend fun rpc(method:String,params:JSONObject=JSONObject(),notification:Boolean=false):JSONObject=withContext(Dispatchers.IO){
  val body=JSONObject().put("jsonrpc","2.0").put("method",method).put("params",params)
  if(!notification) body.put("id",++id)
  val req=Request.Builder().url("$base/mcp/$seat").header("Authorization","Bearer $token").post(body.toString().toRequestBody(media)).build()
  http.newCall(req).execute().use { res ->
   val txt=res.body?.string().orEmpty()
   check(res.isSuccessful) { "HTTP ${res.code}: ${txt.take(250)}" }
   if(notification) JSONObject() else JSONObject(txt).also { check(!it.has("error")) { it.optJSONObject("error")?.toString() ?: "JSON-RPC error" } }
  }
 }
 suspend fun connect():List<DeskTool>{
  rpc("initialize",JSONObject().put("protocolVersion","2024-11-05").put("capabilities",JSONObject()).put("clientInfo",JSONObject().put("name","DioMasteR2D").put("version","0.2.0")))
  rpc("notifications/initialized",notification=true)
  val arr=rpc("tools/list").optJSONObject("result")?.optJSONArray("tools")
  return if(arr==null) emptyList() else (0 until arr.length()).mapNotNull { i -> arr.optJSONObject(i)?.let { DeskTool(it.optString("name"),it.optString("description"),it.optJSONObject("inputSchema")?:JSONObject()) } }
 }
 suspend fun call(name:String,args:JSONObject=JSONObject()):JSONObject=rpc("tools/call",JSONObject().put("name",name).put("arguments",args)).optJSONObject("result")?:JSONObject()
 suspend fun marketCandidates():JSONObject=withContext(Dispatchers.IO) {
  val req=Request.Builder().url("${base.trimEnd('/')}/market/candidates?limit=20").header("Authorization","Bearer $token").get().build()
  http.newCall(req).execute().use { res ->
   val txt=res.body?.string().orEmpty()
   check(res.isSuccessful) { "Market scanner HTTP ${res.code}: ${txt.take(250)}" }
   JSONObject(txt)
  }
 }
 suspend fun marketHome():JSONObject=withContext(Dispatchers.IO) {
  val req=Request.Builder().url("${base.trimEnd('/')}/market/home?limit=20").header("Authorization","Bearer $token").get().build()
  http.newCall(req).execute().use { res ->
   val txt=res.body?.string().orEmpty()
   check(res.isSuccessful) { "Market home HTTP ${res.code}: ${txt.take(250)}" }
   JSONObject(txt)
  }
 }
 suspend fun marketSearch(query:String):JSONObject=withContext(Dispatchers.IO) {
  val encoded=java.net.URLEncoder.encode(query.trim(),"UTF-8")
  val req=Request.Builder().url("${base.trimEnd('/')}/market/search?q=$encoded&limit=20").header("Authorization","Bearer $token").get().build()
  http.newCall(req).execute().use { res ->
   val txt=res.body?.string().orEmpty()
   check(res.isSuccessful) { "Market search HTTP ${res.code}: ${txt.take(250)}" }
   JSONObject(txt)
  }
 }
 suspend fun bloomStatus():JSONObject=withContext(Dispatchers.IO) {
  val req=Request.Builder().url("${base.trimEnd('/')}/bloom/status").header("Authorization","Bearer $token").get().build()
  http.newCall(req).execute().use { res ->
   val txt=res.body?.string().orEmpty()
   check(res.isSuccessful) { "Bloom status HTTP ${res.code}: ${txt.take(250)}" }
   JSONObject(txt)
  }
 }
 suspend fun bloomBalances():JSONObject=withContext(Dispatchers.IO) {
  val req=Request.Builder().url("${base.trimEnd('/')}/bloom/balances").header("Authorization","Bearer $token").get().build()
  http.newCall(req).execute().use { res ->
   val txt=res.body?.string().orEmpty()
   check(res.isSuccessful) { "Wallet balances HTTP ${res.code}: ${txt.take(250)}" }
   JSONObject(txt)
  }
 }
}

@Composable private fun App(){
 val context = LocalContext.current
 // Encrypted preferences are optional: some devices/Keystore states can throw during
 // first Activity composition. Never let credential storage crash the launcher.
 val securePrefs = remember(context) {
  runCatching {
   val masterKey = MasterKey.Builder(context).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build()
   EncryptedSharedPreferences.create(context, "grokbot_secure_prefs", masterKey,
    EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
    EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM)
  }.getOrNull()
 }
 var gateway by remember { mutableStateOf("https://diomaster2d-pumpgrok-gateway.onrender.com") }; var seat by remember { mutableStateOf("chief") }; var token by remember { mutableStateOf(securePrefs?.getString("gateway_token", "") ?: "") }
 var tools by remember { mutableStateOf(emptyList<DeskTool>()) }; var client by remember { mutableStateOf<DeskClient?>(null) }
 var status by remember { mutableStateOf("OFFLINE · PAPER MODE") }; var message by remember { mutableStateOf("Σύνδεσε το Desk Gateway για ζωντανά δεδομένα.") }
 var busy by remember { mutableStateOf(false) }; var tab by remember { mutableIntStateOf(0) }
 var equity by remember { mutableStateOf("--") }; var pnl by remember { mutableStateOf("--") }; var cash by remember { mutableStateOf("--") }
 var bloomReport by remember { mutableStateOf("Bloom wallet not checked") }
 var walletBalance by remember { mutableStateOf<JSONObject?>(null) }
 var walletBalanceMessage by remember { mutableStateOf("Wallet balance not loaded") }; var marketData by remember { mutableStateOf<JSONObject?>(null) }; var homeMarketData by remember { mutableStateOf<JSONObject?>(null) }; var homeMarketMessage by remember { mutableStateOf("Waiting for live multi-source market feed") }; var marketMessage by remember { mutableStateOf("Market scanner not started") }; var marketQuery by remember { mutableStateOf("") }
 var selectedCoin by remember { mutableStateOf<JSONObject?>(null) }; var activity by remember { mutableStateOf(emptyList<String>()) }; var agentStatuses by remember { mutableStateOf(emptyMap<String,String>()) }; var agentAutoRunning by remember { mutableStateOf(false) }; var agentAutoMessage by remember { mutableStateOf("AUTO AGENTS STOPPED") }; var selectedTool by remember { mutableStateOf("") }; var toolArgs by remember { mutableStateOf("{}") }; var toolOutput by remember { mutableStateOf("") }
 val scope= rememberCoroutineScope()
 fun run(block:suspend()->Unit){scope.launch{busy=true;try{block()}catch(e:Exception){message=e.message?: "Σφάλμα σύνδεσης";status="DISCONNECTED"}finally{busy=false}}}
 LaunchedEffect(Unit) {
  if (token.isNotBlank()) run {
   val base=gateway.trim().removeSuffix("/")
   val c=DeskClient(base,seat.trim(),token.trim())
   val found=c.connect()
   securePrefs?.edit()?.putString("gateway_token", token.trim())?.apply()
   client=c;tools=found;status="CONNECTED · BLOOM ONLY · EXECUTION LOCKED"
   message="Αυτόματη σύνδεση επιτυχής · ${found.size} εργαλεία · ${seat.uppercase()}"
   equity="--";cash="--";pnl="--"
   val seats=listOf("chief","scout","risk","whale","sniper","rug","exit","shill","signal","journal")
   val health=linkedMapOf<String,String>()
   for (short in seats) {
    try {
     val seatClient=if(short==seat.trim()) c else DeskClient(base,short,token.trim())
     val seatTools=if(short==seat.trim()) found else seatClient.connect()
     health[short]="CONNECTED · ${seatTools.size} tools"
    } catch(e:Exception) { health[short]="OFFLINE" }
   }
   agentStatuses=health
   try {
    bloomReport=c.bloomStatus().toString(2)
    walletBalance=c.bloomBalances()
    walletBalanceMessage="Confirmed on-chain balances · Jupiter USD pricing"
    val total=walletBalance?.optDouble("total_usd", Double.NaN) ?: Double.NaN
    equity=if(total.isFinite()) "$"+String.format(java.util.Locale.US,"%.2f",total) else "USD price unavailable"
    val first=walletBalance?.optJSONArray("wallets")?.optJSONObject(0)
    cash=if(first!=null) String.format(java.util.Locale.US,"%.4f SOL",first.optDouble("sol",0.0)) else "--"
   } catch(e:Exception) { walletBalanceMessage="Balance read failed: ${e.message ?: "unknown error"}" }
   val checks=listOf("exec_positions","portfolio_exposure","portfolio_pnl","risk_halt_status")
   val reports=mutableListOf<String>()
   for(name in checks) {
    if(found.any { it.name==name }) {
     try { val result=c.call(name,JSONObject()); reports.add("$name · OK") }
     catch(e:Exception) { reports.add("$name · ERROR") }
    }
   }
   activity=(listOf("AUTO START · 10-seat connection sweep complete") + health.map { "${it.key.uppercase()} · ${it.value}" } + reports).take(30)
   message="Auto diagnostics complete · ${health.count{it.value.startsWith("CONNECTED")}}/10 seats online · ${reports.size} checks"
  }
 }
 LaunchedEffect(agentAutoRunning, gateway, token) {
  if (!agentAutoRunning) return@LaunchedEffect
  val seats=listOf("chief","scout","risk","whale","sniper","rug","exit","shill","signal","journal")
  while (agentAutoRunning) {
   val health=linkedMapOf<String,String>()
   for (short in seats) {
    try {
     val seatClient=DeskClient(gateway.trim().removeSuffix("/"),short,token.trim())
     val seatTools=seatClient.connect()
     health[short]="CONNECTED · ${seatTools.size} tools"
    } catch(e:Exception) { health[short]="OFFLINE" }
   }
   agentStatuses=health
   val online=health.count { it.value.startsWith("CONNECTED") }
   val stamp=java.text.SimpleDateFormat("HH:mm:ss",java.util.Locale.getDefault()).format(java.util.Date())
   agentAutoMessage="AUTO AGENT MONITOR · $online/10 seats online · $stamp · PAPER / READ-ONLY"
   activity=(listOf(agentAutoMessage)+health.map { "${it.key.uppercase()} · ${it.value}" }+activity).take(30)
   delay(60_000)
  }
 }
 LaunchedEffect(client) {
  val activeClient = client ?: return@LaunchedEffect
  while (true) {
   try {
    val snapshot = activeClient.marketHome()
    homeMarketData = snapshot
    val count = snapshot.optInt("candidate_count", snapshot.optJSONArray("candidates")?.length() ?: 0)
    val providers = snapshot.optJSONArray("providers")
    val healthy = if (providers == null) 0 else (0 until providers.length()).count { providers.optJSONObject(it)?.optString("status") in listOf("OK", "CONNECTED") }
    val stamp = java.text.SimpleDateFormat("HH:mm:ss", java.util.Locale.getDefault()).format(java.util.Date())
    homeMarketMessage = if (count > 0) "MARKET FEED · $count candidates · $healthy providers · $stamp" else "NO MARKET DATA · $healthy providers responding"
   } catch (e: Exception) {
    homeMarketMessage = "MARKET FEED ERROR · " + (e.message ?: "connection unavailable")
   }
   delay(25_000)
  }
 }
 LaunchedEffect(client, tab, marketQuery) {
  val activeClient = client ?: return@LaunchedEffect
  if (tab == 5) {
   delay(600)
   while (true) {
    try {
     val snapshot = if (marketQuery.isNotBlank()) activeClient.marketSearch(marketQuery) else activeClient.marketHome()
     marketData = snapshot
     val count = snapshot.optInt("candidate_count", snapshot.optJSONArray("candidates")?.length() ?: 0)
     val stamp = java.text.SimpleDateFormat("HH:mm:ss", java.util.Locale.getDefault()).format(java.util.Date())
     marketMessage = "LIVE SCAN · " + count + " candidates · refreshed " + stamp
     delay(25_000)
    } catch (e: Exception) { marketMessage = "SCANNER ERROR · " + (e.message ?: "connection unavailable"); delay(12_000) }
   }
  }
  if (tab == 2) {
   while (true) {
    try {
     val ledgerClient = DeskClient(gateway.trim().removeSuffix("/"), "risk", token.trim())
     val riskTools = ledgerClient.connect()
     if (riskTools.any { it.name == "portfolio_ledger_read" }) {
      val response = ledgerClient.call("portfolio_ledger_read", JSONObject().put("limit", 100))
      val raw = response.optJSONArray("content")?.optJSONObject(0)?.optString("text").orEmpty()
      if (raw.isNotBlank()) {
       val events = JSONObject(raw).optJSONArray("events") ?: org.json.JSONArray()
       val rows = mutableListOf<String>()
       for (i in 0 until events.length()) {
        val event = events.optJSONObject(i) ?: continue
        val payload = event.optJSONObject("payload") ?: JSONObject()
        val type = event.optString("type", "Event")
        val mint = payload.optString("mint", "")
        val symbol = payload.optString("symbol", "")
        val asset = symbol.ifBlank { if (mint.length > 12) mint.take(6) + "…" + mint.takeLast(4) else mint.ifBlank { "—" } }
        val side = payload.optString("side", "").uppercase()
        val detail = when (type) {
         "FillRecorded" -> side + " FILLED · " + asset + " · " + payload.optString("filled_fraction", "—") + " filled"
         "OrderPlaced" -> side + " ORDER · " + asset
         "OrderRejected" -> "ORDER REJECTED · " + asset + " · " + payload.optString("reason", "blocked")
         "PositionOpened" -> "POSITION OPENED · " + asset
         "PositionClosed" -> "POSITION CLOSED · " + asset + " · " + payload.optString("reason", "")
         "JournalNote" -> "AI NOTE · " + payload.optString("note_kind", "analysis") + " · " + asset
         "Escalation" -> "RISK ALERT · " + asset
         else -> type + " · " + asset
        }
        rows.add(event.optString("ts_utc", "") + "\n" + detail + "\nSOURCE: " + event.optString("source", "paper").uppercase())
       }
       activity = rows
       message = if (rows.isEmpty()) "LEDGER ONLINE · no recorded paper fills yet." else "LIVE LEDGER · " + rows.size + " recorded events"
      }
     } else { message = "LEDGER UNAVAILABLE · risk seat has no read permission" }
     delay(15_000)
    } catch (e: Exception) { message = "LEDGER SYNC ERROR · " + (e.message ?: "unavailable"); delay(12_000) }
   }
  }
 }
 val tabs=listOf("Home","Agents","Activity","Tools","Rules","Market")
 Scaffold(containerColor=Bg,bottomBar={NavigationBar(containerColor=Color(0xFF101219),contentColor=Color.White){
  tabs.forEachIndexed { i,s -> NavigationBarItem(selected=tab==i,onClick={tab=i},icon={Text(listOf("⌂","✣","⌁","▦","⚙","◎")[i],fontSize=20.sp)},label={Text(s,fontSize=10.sp)},colors=NavigationBarItemDefaults.colors(selectedIconColor=Red,indicatorColor=Color(0xFF35202A),selectedTextColor=Color.White,unselectedTextColor=Muted)) }
 }}) { pad ->
  LazyColumn(Modifier.fillMaxSize().padding(pad).background(Bg).padding(horizontal=16.dp),verticalArrangement=Arrangement.spacedBy(13.dp),contentPadding=PaddingValues(top=18.dp,bottom=24.dp)){
   item { Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween,verticalAlignment=Alignment.CenterVertically){
    Column { Text("DioMasteR2D Grokbot Trade",fontSize=20.sp,fontWeight=FontWeight.Bold);Text("SOLANA · SECURE DESK",fontSize=10.sp,color=Muted,letterSpacing=2.sp) }
    Column(horizontalAlignment=Alignment.End){Text("●  "+status,fontSize=10.sp,color=if(status.startsWith("CONNECTED")) Green else Red);Text("BLOOM ONLY · EXECUTION LOCKED",fontSize=10.sp,color=Red)}
   }}
   when(tab){
    0 -> {
     item { CardBox { Column {
      Text("PORTFOLIO · VERIFIED DATA ONLY",fontSize=11.sp,color=Muted,letterSpacing=1.5.sp)
      Text(equity,fontSize=36.sp,fontWeight=FontWeight.Bold,color=Color.White)
      Text("No verified wallet balance loaded",fontSize=11.sp,color=Muted)
      Spacer(Modifier.height(10.dp));Row(horizontalArrangement=Arrangement.spacedBy(18.dp)){Metric("P&L",pnl,Green);Metric("CASH",cash,Color.White)}
      Spacer(Modifier.height(12.dp));Text("Chart waiting for verified market and wallet data.",fontSize=11.sp,color=Muted)
     }}
     }
     item { Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween){Text("AGENT NETWORK",fontSize=18.sp,fontWeight=FontWeight.Bold);Text("${tools.size} TOOLS",fontSize=11.sp,color=Green)} }
     item { AgentOrbit(agentStatuses) }
     item { Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween,verticalAlignment=Alignment.CenterVertically) {
      Column { Text("LIVE SOLANA MARKET",fontSize=18.sp,fontWeight=FontWeight.Bold); Text("TRENDING · NEW PAIRS · BOT DECISIONS",fontSize=9.sp,color=Muted,letterSpacing=1.sp) }
      Text(if ((homeMarketData?.optInt("candidate_count") ?: 0) > 0) "● LIVE" else "● WAITING",fontSize=10.sp,color=if ((homeMarketData?.optInt("candidate_count") ?: 0) > 0) Green else Muted)
     } }
     item { CardBox { Column(verticalArrangement=Arrangement.spacedBy(7.dp)) {
      Text(homeMarketMessage,fontSize=10.sp,color=Muted)
      val providers=homeMarketData?.optJSONArray("providers")
      if(providers!=null) {
       val providerLine=(0 until providers.length()).mapNotNull { providers.optJSONObject(it) }.joinToString("  ·  ") { it.optString("name")+" "+it.optString("status") }
       Text(providerLine,fontSize=9.sp,color=Blue)
      }
      val stream=homeMarketData?.optJSONObject("pumpportal_stream")
      Text("PUMPPORTAL STREAM · "+(if(stream?.optBoolean("connected")==true) "CONNECTED" else "RECONNECTING / NOT CONNECTED"),fontSize=10.sp,color=if(stream?.optBoolean("connected")==true) Green else Muted)
      Text("Rule-based agent assessments · unverified tokens remain blocked · no live orders.",fontSize=10.sp,color=Red)
      OutlinedButton(onClick={tab=5},modifier=Modifier.fillMaxWidth()) { Text("OPEN FULL MARKET & SEARCH COINS") }
     } } }
     val homeCandidates=homeMarketData?.optJSONArray("candidates")
     val homeRows=if(homeCandidates==null) emptyList() else (0 until homeCandidates.length()).mapNotNull { homeCandidates.optJSONObject(it) }
     if(homeRows.isEmpty()) item { CardBox { Text("Waiting for market providers. Connect the gateway to load trending coins.",fontSize=11.sp,color=Muted) } }
     else items(homeRows.size) { idx ->
      val coin=homeRows[idx]
      val price=coin.optDouble("price_usd",Double.NaN)
      val liquidity=coin.optDouble("liquidity_usd",Double.NaN)
      val volume=coin.optDouble("volume_24h_usd",Double.NaN)
      val change=coin.optDouble("price_change_1h_pct",Double.NaN)
      val agents=coin.optJSONArray("agents")
      val decisionLine=if(agents==null) "Agent assessment unavailable" else (0 until agents.length()).mapNotNull { agents.optJSONObject(it) }.joinToString("  ·  ") { it.optString("agent")+": "+it.optString("decision") }
      CardBox { Column(Modifier.fillMaxWidth().clickable { selectedCoin=coin; marketQuery=coin.optString("mint",""); tab=5 },verticalArrangement=Arrangement.spacedBy(6.dp)) {
       Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween,verticalAlignment=Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
         Text(coin.optString("symbol","—")+" · "+coin.optString("name","Unknown"),fontWeight=FontWeight.Bold,color=Color.White)
         Text(coin.optString("trend","MARKET")+" · "+coin.optJSONArray("source")?.let { a -> (0 until a.length()).joinToString(" + ") { a.optString(it) } }.orEmpty(),fontSize=9.sp,color=Blue)
        }
        Text(if(change.isFinite()) String.format(java.util.Locale.US,"%+.1f%%",change) else "—",fontSize=13.sp,color=if(change.isFinite()&&change>=0)Green else Red,fontWeight=FontWeight.Bold)
       }
       Text(coin.optString("mint","").let { if(it.length>16) it.take(7)+"…"+it.takeLast(5) else it },fontSize=9.sp,color=Muted)
       Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween) {
        Metric("PRICE",if(price.isFinite()) "$"+String.format(java.util.Locale.US,"%.8f",price) else "N/A",Blue)
        Metric("LIQ",if(liquidity.isFinite()) "$"+String.format(java.util.Locale.US,"%.0f",liquidity) else "N/A",Color.White)
        Metric("VOL 24H",if(volume.isFinite()) "$"+String.format(java.util.Locale.US,"%.0f",volume) else "N/A",Green)
       }
       Text(decisionLine,fontSize=9.sp,color=Color.White)
       Text("TAP COIN FOR FULL MARKET SEARCH",fontSize=8.sp,color=Blue)
       Text(coin.optString("risk_gate","BLOCKED · SAFETY NOT VERIFIED"),fontSize=9.sp,color=Red,fontWeight=FontWeight.Bold)
      } }
     }

     item { CardBox { Column(verticalArrangement=Arrangement.spacedBy(9.dp)) {
      Text("BLOOM WALLET · VERIFIED BALANCES",fontSize=13.sp,fontWeight=FontWeight.Bold,color=Blue)
      Text(walletBalanceMessage,fontSize=10.sp,color=Muted)
      val wallets=walletBalance?.optJSONArray("wallets")
      if(wallets==null || wallets.length()==0) {
       Text("No wallet balance loaded yet.",fontSize=12.sp,color=Muted)
      } else {
       for(w in 0 until wallets.length()) {
        val wallet=wallets.optJSONObject(w) ?: continue
        val address=wallet.optString("address")
        Text("${wallet.optString("label","Wallet")} · ${if(address.length>14) address.take(6)+"…"+address.takeLast(5) else address}",fontSize=11.sp,color=Color.White,fontWeight=FontWeight.Bold)
        Text(String.format(java.util.Locale.US,"%.6f SOL",wallet.optDouble("sol",0.0)),fontSize=20.sp,color=Green,fontWeight=FontWeight.Bold)
        val solUsd=wallet.optDouble("sol_usd",Double.NaN)
        Text(if(solUsd.isFinite()) "SOL value: $"+String.format(java.util.Locale.US,"%.2f",solUsd) else "SOL USD price unavailable",fontSize=10.sp,color=Muted)
        val tokens=wallet.optJSONArray("tokens")
        if(tokens!=null) for(t in 0 until tokens.length()) {
         val asset=tokens.optJSONObject(t) ?: continue
         val mint=asset.optString("mint")
         val value=asset.optDouble("usd_value",Double.NaN)
         Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween) {
          Text(mint.take(5)+"…"+mint.takeLast(4)+" · "+String.format(java.util.Locale.US,"%.4f",asset.optDouble("amount",0.0)),fontSize=10.sp,color=Color.White)
          Text(if(value.isFinite()) "$"+String.format(java.util.Locale.US,"%.2f",value) else "Price N/A",fontSize=10.sp,color=if(value.isFinite())Green else Muted)
         }
        }
       }
       val total=walletBalance?.optDouble("total_usd",Double.NaN) ?: Double.NaN
       Text(if(total.isFinite()) "TOTAL VERIFIED VALUE · $"+String.format(java.util.Locale.US,"%.2f",total) else "TOTAL USD VALUE · NOT AVAILABLE",fontSize=16.sp,color=Green,fontWeight=FontWeight.Bold)
       WalletSparkline()
      }
      Text("Bloom wallet list + confirmed Solana RPC balances + Jupiter indicative USD prices.",fontSize=10.sp,color=Muted)
      Button(onClick={run {
       val c=client ?: error("Συνδέσου πρώτα στο Gateway")
       bloomReport=c.bloomStatus().toString(2)
       walletBalance=c.bloomBalances()
       walletBalanceMessage="Updated just now · confirmed chain state"
       val total=walletBalance?.optDouble("total_usd",Double.NaN) ?: Double.NaN
       equity=if(total.isFinite()) "$"+String.format(java.util.Locale.US,"%.2f",total) else "USD price unavailable"
       val first=walletBalance?.optJSONArray("wallets")?.optJSONObject(0)
       cash=if(first!=null) String.format(java.util.Locale.US,"%.4f SOL",first.optDouble("sol",0.0)) else "--"
       activity=(listOf("WALLET REFRESH · on-chain balances updated") + activity).take(30)
      }},enabled=!busy&&client!=null,modifier=Modifier.fillMaxWidth(),colors=ButtonDefaults.buttonColors(containerColor=Red)){Text(if(busy)"REFRESHING..." else "REFRESH BLOOM BALANCE")}
      Text("READ ONLY · No orders are sent from this screen.",fontSize=10.sp,color=Muted)
     }} }
     item { CardBox { Column(verticalArrangement=Arrangement.spacedBy(5.dp)) {
      Text("AUTO DIAGNOSTICS",fontSize=13.sp,fontWeight=FontWeight.Bold,color=Blue)
      Text(message,fontSize=11.sp,color=Muted)
      Text("Read-only checks run automatically on startup. Scanner waits for a verified mint; no automatic orders are sent.",fontSize=10.sp,color=Green)
     } } }
     item { Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween){Text("RECENT ACTIVITY",fontSize=18.sp,fontWeight=FontWeight.Bold);Text("LEDGER",fontSize=10.sp,color=Green)} }
     if(activity.isEmpty()) item { CardBox { Text(message,fontSize=12.sp,color=Muted) } } else items(activity.take(12)){line->CardBox{Text(line,fontSize=12.sp,color=Color.White)}}
    }
    1 -> {
     item { Text("PUMPGROK AGENT NETWORK",fontSize=20.sp,fontWeight=FontWeight.Bold) }
     item { CardBox { Text("10 specialist seats · PumpGrok role definitions. Tool access is controlled by the server roster.",fontSize=12.sp,color=Muted) } }
     item { CardBox { Column(verticalArrangement=Arrangement.spacedBy(8.dp)) {
      Text(agentAutoMessage,fontSize=11.sp,color=if(agentAutoRunning) Green else Muted,fontWeight=FontWeight.Bold)
      Text("Η αυτόματη λειτουργία ελέγχει ανά 60″ τη σύνδεση και τα διαθέσιμα εργαλεία των 10 seats. Είναι PAPER / READ-ONLY: δεν στέλνει εντολές αγοράς ή πώλησης.",fontSize=10.sp,color=Muted)
      Button(onClick={
       if(agentAutoRunning) {
        agentAutoRunning=false
        agentAutoMessage="AUTO AGENTS STOPPED"
       } else {
        require(token.isNotBlank()) { "Βάλε πρώτα το gateway token στις Rules." }
        require(gateway.startsWith("https://")) { "Χρειάζεται HTTPS gateway." }
        agentAutoRunning=true
        agentAutoMessage="STARTING · checking 10 agent seats..."
       }
      },enabled=!busy,modifier=Modifier.fillMaxWidth(),colors=ButtonDefaults.buttonColors(containerColor=if(agentAutoRunning) Color(0xFF8B3030) else Green,contentColor=Color.Black)) {
       Text(if(agentAutoRunning) "STOP AUTO AGENTS" else "START AUTO AGENTS")
      }
     } } }
     item { CardBox { Column(verticalArrangement=Arrangement.spacedBy(8.dp)) {
      Text("ACTIVE AGENT SEAT",fontSize=12.sp,fontWeight=FontWeight.Bold,color=Blue)
      OutlinedTextField(seat,{seat=it.trim().lowercase()},modifier=Modifier.fillMaxWidth(),singleLine=true,label={Text("chief / scout / risk / whale / sniper / rug / exit / shill / signal / journal")})
      Button(onClick={run {
       val c=DeskClient(gateway.trim().removeSuffix("/"),seat.trim().lowercase(),token.trim())
       val found=c.connect()
       securePrefs?.edit()?.putString("gateway_token", token.trim())?.apply()
       client=c;tools=found;status="CONNECTED · BLOOM ONLY · EXECUTION LOCKED"
       message="Connected to ${seat.uppercase()} · ${found.size} permitted tools"
       activity=listOf("Seat switched to ${seat.uppercase()} · ${found.size} tools loaded")
      }},enabled=!busy&&seat.isNotBlank()&&token.isNotBlank(),modifier=Modifier.fillMaxWidth(),colors=ButtonDefaults.buttonColors(containerColor=Red)){Text(if(busy)"CONNECTING..." else "CONNECT SELECTED AGENT")}
      Text("Κάθε seat εμφανίζει μόνο τα εργαλεία που του επιτρέπει το PumpGrok roster.",fontSize=10.sp,color=Muted)
     } } }
     item { Column(verticalArrangement=Arrangement.spacedBy(9.dp)) {
      Row(horizontalArrangement=Arrangement.spacedBy(9.dp)) { AgentCard("CHIEF","Desk orchestrator","CHIEF",Color(0xFFFFC857),Modifier.weight(1f)); AgentCard("SCOUT","Token discovery","SCOUT",Color(0xFF26D6C5),Modifier.weight(1f)) }
      Row(horizontalArrangement=Arrangement.spacedBy(9.dp)) { AgentCard("RISK","Absolute safety gate","RISK",Green,Modifier.weight(1f)); AgentCard("WHALE","Smart-money analyst","WHALE",Blue,Modifier.weight(1f)) }
      Row(horizontalArrangement=Arrangement.spacedBy(9.dp)) { AgentCard("SNIPER","Entry specialist","SNIPER",Red,Modifier.weight(1f)); AgentCard("RUG","Rug safety monitor","RUG",Color(0xFFFFA34D),Modifier.weight(1f)) }
      Row(horizontalArrangement=Arrangement.spacedBy(9.dp)) { AgentCard("EXIT","Position manager","EXIT",Color(0xFF26D6C5),Modifier.weight(1f)); AgentCard("SHILL","Sentiment analyst","SHILL",Purple,Modifier.weight(1f)) }
      Row(horizontalArrangement=Arrangement.spacedBy(9.dp)) { AgentCard("SIGNAL","Momentum scorer","SIGNAL",Blue,Modifier.weight(1f)); AgentCard("JOURNAL","Trade journal","JOURNAL",Color(0xFFFFC857),Modifier.weight(1f)) }
     } }
    }
    2 -> {
     item { Text("ACTIVITY & PAPER LEDGER",fontSize=20.sp,fontWeight=FontWeight.Bold) }
     item { CardBox { Column(verticalArrangement=Arrangement.spacedBy(8.dp)) {
      Text("PAPER EXECUTION HISTORY",fontSize=12.sp,fontWeight=FontWeight.Bold,color=Blue)
      Text("Οι εγγραφές προέρχονται από το append-only ledger του server. Δεν εμφανίζονται εικονικές κινήσεις όταν δεν υπάρχουν fills.",fontSize=10.sp,color=Muted)
      Button(onClick={run {
       val base=gateway.trim().removeSuffix("/")
       val ledgerClient=DeskClient(base,"risk",token.trim())
       val riskTools=ledgerClient.connect()
       require(riskTools.any { it.name=="portfolio_ledger_read" }) { "Το risk seat δεν διαθέτει portfolio ledger read." }
       val response=ledgerClient.call("portfolio_ledger_read",JSONObject().put("limit",100))
       val content=response.optJSONArray("content")
       val raw=content?.optJSONObject(0)?.optString("text").orEmpty()
       check(raw.isNotBlank()) { "Ο server δεν επέστρεψε δεδομένα ledger." }
       val data=JSONObject(raw)
       val events=data.optJSONArray("events") ?: org.json.JSONArray()
       val rows=mutableListOf<String>()
       for(i in 0 until events.length()) {
        val event=events.optJSONObject(i) ?: continue
        val payload=event.optJSONObject("payload") ?: JSONObject()
        val type=event.optString("type","Event")
        val side=payload.optString("side","").uppercase()
        val mint=payload.optString("mint","")
        val symbol=payload.optString("symbol","")
        val asset=if(symbol.isNotBlank()) symbol else if(mint.length>12) mint.take(6)+"…"+mint.takeLast(4) else mint.ifBlank { "—" }
        val source=event.optString("source","paper").uppercase()
        val time=event.optString("ts_utc","")
        val detail=when(type) {
         "FillRecorded" -> "$side FILLED · $asset · ${payload.optString("filled_fraction","—")} filled"
         "OrderPlaced" -> "$side ORDER · $asset · ${payload.optString("ticket_id","")}"
         "OrderRejected" -> "ORDER REJECTED · ${payload.optString("reason","unknown")} · $asset"
         "PositionOpened" -> "POSITION OPENED · $asset"
         "PositionClosed" -> "POSITION CLOSED · $asset · ${payload.optString("reason","")}"
         "JournalNote" -> "AGENT NOTE · ${payload.optString("note_kind","note")} · $asset"
         "Escalation" -> "RISK ALERT · $asset"
         else -> "$type · $asset"
        }
        rows.add("$time\n$detail\nSOURCE: $source")
       }
       activity=rows
       message=if(rows.isEmpty()) "Ledger connected · no paper trades recorded yet." else "Loaded ${rows.size} real ledger events."
      }},enabled=!busy&&token.isNotBlank(),modifier=Modifier.fillMaxWidth(),colors=ButtonDefaults.buttonColors(containerColor=Red)){Text(if(busy)"LOADING LEDGER..." else "REFRESH PAPER ACTIVITY")}
     } } }
     if(activity.isEmpty()) item { CardBox { Text("Δεν υπάρχουν ακόμη εγγεγραμμένες κινήσεις. Πάτησε REFRESH PAPER ACTIVITY για έλεγχο.",color=Muted) } }
     items(activity){line->CardBox{Text(line,fontSize=12.sp,color=Color.White)}}
    }
    3 -> {
     item { Text("PUMPGROK TOOLS · ${tools.size}",fontSize=20.sp,fontWeight=FontWeight.Bold) }
     item { CardBox { Column(verticalArrangement=Arrangement.spacedBy(8.dp)) {
      Text("TOOL CONSOLE",fontSize=14.sp,fontWeight=FontWeight.Bold,color=Red)
      OutlinedTextField(selectedTool,{selectedTool=it},modifier=Modifier.fillMaxWidth(),singleLine=true,label={Text("Selected server tool")})
      OutlinedTextField(toolArgs,{toolArgs=it},modifier=Modifier.fillMaxWidth(),minLines=3,label={Text("Arguments · JSON")})
      Button(onClick={run {
       val c=client ?: error("Συνδέσου πρώτα στο Gateway")
       val result=c.call(selectedTool.trim(),JSONObject(toolArgs))
       toolOutput=result.toString()
       activity=(listOf("Tool: $selectedTool",toolOutput)+activity).take(30)
      }},enabled=!busy&&client!=null&&selectedTool.isNotBlank(),modifier=Modifier.fillMaxWidth(),colors=ButtonDefaults.buttonColors(containerColor=Red)){Text(if(busy)"RUNNING..." else "RUN SELECTED TOOL")}
      if(toolOutput.isNotBlank()) Text(toolOutput,fontSize=11.sp,color=Green)
     } } }
     if(tools.isEmpty()) item { CardBox { Text("Δεν φορτώθηκαν εργαλεία. Έλεγξε τη σύνδεση από Rules.",color=Muted) } }
     items(tools){t->CardBox { Column(Modifier.fillMaxWidth().clickable { selectedTool=t.name; toolArgs="{}"; toolOutput="" },verticalArrangement=Arrangement.spacedBy(5.dp)) { Text(t.name,color=Green,fontWeight=FontWeight.Bold); Text(t.description,color=Muted,fontSize=12.sp); Text("TAP TO SELECT",fontSize=9.sp,color=Blue) } } }
    }
    4 -> {
     item { Text("DESK CONNECTION",fontSize=20.sp,fontWeight=FontWeight.Bold) }
     item { CardBox { Column(verticalArrangement=Arrangement.spacedBy(10.dp)){
      Text("Gateway HTTPS URL",color=Muted,fontSize=12.sp);OutlinedTextField(gateway,{gateway=it},modifier=Modifier.fillMaxWidth(),singleLine=true,placeholder={Text("https://your-secure-gateway")})
      Text("Seat",color=Muted,fontSize=12.sp);OutlinedTextField(seat,{seat=it.trim().lowercase()},modifier=Modifier.fillMaxWidth(),singleLine=true)
      Text("Bearer token",color=Muted,fontSize=12.sp);OutlinedTextField(token,{token=it},modifier=Modifier.fillMaxWidth(),singleLine=true,visualTransformation=PasswordVisualTransformation())
      Button(onClick={run{
       require(gateway.startsWith("https://")){"Χρειάζεται ασφαλής HTTPS διεύθυνση gateway."}
       val c=DeskClient(gateway.trim().removeSuffix("/"),seat.trim(),token.trim());val found=c.connect()
       securePrefs?.edit()?.putString("gateway_token", token.trim())?.apply()
       client=c;tools=found;status="CONNECTED · BLOOM ONLY · EXECUTION LOCKED";message="Συνδέθηκε. Φορτώθηκαν ${found.size} εργαλεία για το seat ${seat.uppercase()}."
        bloomReport=c.bloomStatus().toString(2)
        equity="--";cash="--";pnl="--";activity=listOf("Gateway connected · ${found.size} tools loaded · ${seat.uppercase()} seat")
      }},enabled=!busy&&gateway.isNotBlank()&&token.isNotBlank(),modifier=Modifier.fillMaxWidth(),colors=ButtonDefaults.buttonColors(containerColor=Red)){Text(if(busy)"CONNECTING..." else "CONNECT DESK")}
      Text(message,fontSize=11.sp,color=Muted)
      Text("BLOOM WALLET ONLY · All bot transactions will route through the Bloom server API. No Phantom connection or seed phrase is used.",fontSize=11.sp,color=Green)
      Text("BLOOM EXECUTION NOT ACTIVE · BUY/SELL remains locked until the server adapter, risk checks and on-chain confirmation are tested.",fontSize=11.sp,color=Red)
            Text("Το token μένει μόνο στη μνήμη της εφαρμογής. Μην βάλεις seed phrase ή private key.",fontSize=11.sp,color=Green)
     }}}
     item { CardBox { Text("Live trading remains locked. Never reuse a token previously embedded in an APK; rotate gateway seat tokens in Render.",color=Red,fontSize=12.sp) } }
    }
    else -> {
     item { Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween) {
      Column { Text("SOLANA MARKET",fontSize=20.sp,fontWeight=FontWeight.Bold); Text("MULTI-SOURCE · BLOOM-ONLY EXECUTION TARGET",fontSize=10.sp,color=Muted) }
      Text("SCANNER",fontSize=10.sp,color=Green)
     } }
     item { CardBox { Column(verticalArrangement=Arrangement.spacedBy(8.dp)) {
      Text("ΑΝΑΖΗΤΗΣΗ SOLANA COINS · SYMBOL / NAME / MINT",fontSize=10.sp,color=Blue,fontWeight=FontWeight.Bold)
      OutlinedTextField(value=marketQuery,onValueChange={marketQuery=it},modifier=Modifier.fillMaxWidth(),singleLine=true,label={Text("π.χ. BONK, WIF ή mint address")},placeholder={Text("Search coins across Solana DEX pairs")})
      Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(8.dp)) {
       Button(onClick={run {
        require(marketQuery.isNotBlank()) { "Γράψε όνομα, σύμβολο ή mint coin." }
        val c=client ?: error("Συνδέσου πρώτα στο Gateway")
        marketData=c.marketSearch(marketQuery)
        val count=marketData?.optInt("candidate_count",0) ?: 0
        marketMessage="SEARCH RESULTS · $count Solana pairs · read-only"
        activity=(listOf("MARKET SEARCH · "+marketQuery+" · "+count+" results") + activity).take(30)
       }},enabled=!busy&&token.isNotBlank()&&marketQuery.isNotBlank(),modifier=Modifier.weight(1f),colors=ButtonDefaults.buttonColors(containerColor=Red)){Text(if(busy)"SEARCHING..." else "SEARCH COINS")}
       OutlinedButton(onClick={marketQuery="";run {
        val c=client ?: error("Συνδέσου πρώτα στο Gateway")
        marketData=c.marketCandidates()
        marketMessage="LIVE DISCOVERY · latest Solana pools"
       }},enabled=!busy&&token.isNotBlank(),modifier=Modifier.weight(1f)){Text("LATEST COINS")}
      }
      Text(marketMessage,fontSize=11.sp,color=Muted)
      Text("LIQUIDITY >= USD 40K · MINT/FREEZE REVOKED · TOP10 <=25% · SCORE >=70",fontSize=10.sp,color=Blue)
      Text("TP +70%…+130% · SL -6% · TRAIL -12% · SIZE 8% EQUITY",fontSize=10.sp,color=Green)
      Button(onClick={run {
       val c=client ?: error("Συνδέσου πρώτα στο Gateway")
       marketData=c.marketCandidates()
       val count=marketData?.optInt("candidate_count",0) ?: 0
       marketMessage="Updated · $count candidates · read-only scanner"
       activity=(listOf("MARKET SCAN · $count candidates") + activity).take(30)
      }},enabled=!busy&&token.isNotBlank(),modifier=Modifier.fillMaxWidth(),colors=ButtonDefaults.buttonColors(containerColor=Red)){Text(if(busy)"SCANNING..." else "SCAN MARKET NOW")}
     } } }
     selectedCoin?.let { coin ->
      val mint=coin.optString("mint","")
      val price=coin.optDouble("price_usd",Double.NaN)
      val change=coin.optDouble("price_change_24h_pct",Double.NaN)
      item { CardBox { Column(verticalArrangement=Arrangement.spacedBy(9.dp)) {
       Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween,verticalAlignment=Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
         Text(coin.optString("symbol","—")+" · "+coin.optString("name","Unknown"),fontSize=18.sp,fontWeight=FontWeight.Bold)
         Text("SOLANA · LIVE MARKET CHART",fontSize=9.sp,color=Blue)
        }
        TextButton(onClick={selectedCoin=null}) { Text("CLOSE") }
       }
       Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween) {
        Metric("PRICE",if(price.isFinite()) "$"+String.format(java.util.Locale.US,"%.10f",price) else "N/A",Blue)
        Metric("24H CHANGE",if(change.isFinite()) String.format(java.util.Locale.US,"%+.2f%%",change) else "N/A",if(change.isFinite()&&change>=0) Green else Red)
        Metric("LIQUIDITY",coin.optDouble("liquidity_usd",Double.NaN).let { if(it.isFinite()) "$"+String.format(java.util.Locale.US,"%.0f",it) else "N/A" },Color.White)
       }
       Text("PRICE CHART · DEXSCREENER",fontSize=11.sp,color=Blue,fontWeight=FontWeight.Bold)
       if(mint.isNotBlank()) {
        AndroidView(
         modifier=Modifier.fillMaxWidth().height(390.dp),
         factory={ context ->
          WebView(context).apply {
           settings.javaScriptEnabled=true
           settings.domStorageEnabled=true
           settings.loadsImagesAutomatically=true
           webViewClient=WebViewClient()
           loadUrl("https://dexscreener.com/solana/"+mint+"?embed=1&theme=dark&trades=0&info=0")
          }
         },
         update={ view ->
          val target="https://dexscreener.com/solana/"+mint+"?embed=1&theme=dark&trades=0&info=0"
          if(view.tag!=target) { view.tag=target; view.loadUrl(target) }
         }
        )
       } else Text("Chart unavailable: token mint missing.",fontSize=11.sp,color=Muted)
       Text("Read-only market view · no buy/sell actions.",fontSize=10.sp,color=Muted)
      } } }
     }
     val candidates=marketData?.optJSONArray("candidates")
     val candidateRows=if(candidates==null) emptyList() else (0 until candidates.length()).mapNotNull { candidates.optJSONObject(it) }
     if(candidateRows.isEmpty()) item { CardBox { Text("Δεν βρέθηκαν coins. Κάνε αναζήτηση ή πάτησε LATEST COINS.",fontSize=12.sp,color=Muted) } }
     else items(candidateRows.size) { idx ->
      val coin=candidateRows[idx]
      val checks=coin.optJSONObject("checks") ?: JSONObject()
      val onchain=coin.optJSONObject("onchain") ?: JSONObject()
      val mint=coin.optString("mint")
      val liq=coin.optDouble("liquidity_usd",Double.NaN)
      val price=coin.optDouble("price_usd",Double.NaN)
      CardBox { Column(Modifier.fillMaxWidth().clickable { selectedCoin=coin },verticalArrangement=Arrangement.spacedBy(6.dp)) {
       Row(Modifier.fillMaxWidth(), verticalAlignment=Alignment.CenterVertically, horizontalArrangement=Arrangement.spacedBy(10.dp)) {
  CoinPulseBadge(coin.optString("symbol", "SOL"))
  Column(Modifier.weight(1f)) {
   Text(coin.optString("symbol","—")+" · "+coin.optString("name","Unknown"),fontWeight=FontWeight.Bold,color=Color.White)
   Text("LIVE MARKET CANDIDATE",fontSize=8.sp,color=Blue,letterSpacing=1.sp)
  }
  Text("●", color=Green, fontSize=12.sp)
 }
       Text(mint.take(7)+"…"+mint.takeLast(5),fontSize=9.sp,color=Muted)
       Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween) {
        Metric("PRICE",if(price.isFinite()) "$"+String.format(java.util.Locale.US,"%.8f",price) else "N/A",Blue)
        Metric("LIQUIDITY",if(liq.isFinite()) "$"+String.format(java.util.Locale.US,"%.0f",liq) else "N/A",Color.White)
        Metric("AI SCORE",if(coin.isNull("ai_score")) "N/A" else coin.optString("ai_score"),Red)
       }
       Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween) {
        val vol=coin.optDouble("volume_24h_usd",Double.NaN)
        val cap=coin.optDouble("market_cap_usd",Double.NaN)
        Metric("VOL 24H",if(vol.isFinite()) "$"+String.format(java.util.Locale.US,"%.0f",vol) else "N/A",Green)
        Metric("MKT CAP",if(cap.isFinite()) "$"+String.format(java.util.Locale.US,"%.0f",cap) else "N/A",Color.White)
        Metric("SOURCE",coin.optJSONArray("source")?.optString(0) ?: "DEX",Blue)
       }
       Text("Mint revoked: "+checks.optBoolean("mint_authority",false)+" · Freeze revoked: "+checks.optBoolean("freeze_authority",false)+" · Top10: "+(if(onchain.isNull("top10_share"))"N/A" else String.format(java.util.Locale.US,"%.1f%%",onchain.optDouble("top10_share")*100)),fontSize=10.sp,color=Muted)
       Text("BUY DISABLED · "+(coin.optJSONArray("blockers")?.let { a -> (0 until a.length()).joinToString { a.optString(it) } } ?: "Awaiting checks"),fontSize=10.sp,color=Red)
      } }
     }
    }
   }
  }
 }
}
@Composable private fun AgentOrbit(statuses:Map<String,String>) {
 val names=listOf("CHIEF","SCOUT","RISK","WHALE","SNIPER","RUG","EXIT","SHILL","SIGNAL","JOURNAL")
 val colors=listOf(Color(0xFFFFC857),Color(0xFF26D6C5),Green,Blue,Red,Color(0xFFFFA34D),Color(0xFF26D6C5),Purple,Blue,Color(0xFFFFC857))
 val transition= rememberInfiniteTransition(label="agent-orbit")
 val angle by transition.animateFloat(initialValue=0f,targetValue=360f,animationSpec=infiniteRepeatable(tween(18000,easing=FastOutSlowInEasing),RepeatMode.Restart),label="orbit-angle")
 Box(Modifier.fillMaxWidth().height(292.dp),contentAlignment=Alignment.Center) {
  Canvas(Modifier.size(250.dp)) {
   val center=androidx.compose.ui.geometry.Offset(size.width/2f,size.height/2f)
   val radius=size.minDimension*.46f
   drawCircle(color=Blue.copy(alpha=.16f),radius=radius,center=center,style=androidx.compose.ui.graphics.drawscope.Stroke(width=1.dp.toPx()))
   drawCircle(color=Purple.copy(alpha=.22f),radius=radius*.68f,center=center,style=androidx.compose.ui.graphics.drawscope.Stroke(width=1.dp.toPx()))
   for(i in 0 until 10) {
    val a=Math.toRadians(i*36.0+angle-90.0)
    val node=androidx.compose.ui.geometry.Offset(center.x+(kotlin.math.cos(a)*radius).toFloat(),center.y+(kotlin.math.sin(a)*radius).toFloat())
    drawLine(colors[i].copy(alpha=.16f),center,node,strokeWidth=1.dp.toPx())
    val moving=Math.toRadians(i*36.0-angle*2.0)
    val dot=androidx.compose.ui.geometry.Offset(center.x+(kotlin.math.cos(moving)*radius*.82f).toFloat(),center.y+(kotlin.math.sin(moving)*radius*.82f).toFloat())
    drawCircle(colors[i],radius=3.dp.toPx(),center=dot)
   }
   drawCircle(color=Purple.copy(alpha=.10f),radius=radius*.42f,center=center)
  }
  Column(horizontalAlignment=Alignment.CenterHorizontally) {
   Text("DioMasteR2D",fontSize=17.sp,fontWeight=FontWeight.Bold,color=Color.White)
   Text("10 AGENT NETWORK",fontSize=9.sp,color=Green,letterSpacing=1.5.sp)
   Text("${statuses.values.count{it.startsWith("CONNECTED")}} / 10 ONLINE",fontSize=10.sp,color=Muted)
  }
  names.forEachIndexed { i,name ->
   val radians=Math.toRadians((i*36.0+angle-90.0))
   val radius=112.0
   val x=(cos(radians)*radius).dp
   val y=(sin(radians)*radius).dp
   Column(Modifier.offset(x=x,y=y).width(58.dp),horizontalAlignment=Alignment.CenterHorizontally) {
    Box(Modifier.size(34.dp).background(colors[i].copy(alpha=if(statuses[name.lowercase()]?.startsWith("CONNECTED")==true) .25f else .08f),RoundedCornerShape(50)),contentAlignment=Alignment.Center) {
     Text("✦",fontSize=18.sp,color=colors[i])
    }
    Text(name,fontSize=7.sp,color=if(statuses[name.lowercase()]?.startsWith("ONLINE")==true) Green else Muted,maxLines=1)
   }
  }
 }
}
@Composable private fun CoinPulseBadge(symbol: String) {
 val pulse = rememberInfiniteTransition(label = "coin-pulse")
 val scale by pulse.animateFloat(0.92f, 1.08f, infiniteRepeatable(tween(900, easing = FastOutSlowInEasing), RepeatMode.Reverse), label = "coin-scale")
 val glow by pulse.animateFloat(0.22f, 0.72f, infiniteRepeatable(tween(900), RepeatMode.Reverse), label = "coin-glow")
 Box(Modifier.size(46.dp).background(Blue.copy(alpha = glow * 0.18f), RoundedCornerShape(15.dp)), contentAlignment = Alignment.Center) {
  Text(symbol.take(1).uppercase(), fontSize = (19f * scale).sp, fontWeight = FontWeight.Black, color = Blue)
 }
}
@Composable private fun CardBox(content:@Composable ColumnScope.()->Unit){Card(colors=CardDefaults.cardColors(containerColor=Panel),shape=RoundedCornerShape(18.dp),modifier=Modifier.fillMaxWidth()){Column(Modifier.padding(16.dp),content=content)}}
@Composable private fun Metric(label:String,value:String,color:Color){Column{Text(label,fontSize=10.sp,color=Muted);Text(value,fontSize=17.sp,fontWeight=FontWeight.Bold,color=color)}}
@Composable private fun AgentCard(name:String,desc:String,id:String,color:Color,modifier:Modifier=Modifier){Card(modifier,colors=CardDefaults.cardColors(containerColor=Panel),shape=RoundedCornerShape(16.dp)){Column(Modifier.fillMaxWidth().padding(12.dp),verticalArrangement=Arrangement.spacedBy(3.dp)){Text("✦",fontSize=22.sp,color=color);Text(name,fontWeight=FontWeight.Bold,fontSize=13.sp);Text(desc,fontSize=10.sp,color=Muted,maxLines=2);Text("AGENT $id",fontSize=9.sp,color=color)}}}
@Composable private fun WalletSparkline(){
 val transition=rememberInfiniteTransition(label="wallet-chart")
 val phase by transition.animateFloat(0f,1f,infiniteRepeatable(tween(2400,easing=FastOutSlowInEasing),RepeatMode.Restart),label="chart-flow")
 Canvas(Modifier.fillMaxWidth().height(82.dp)){
  val p=Path().apply{
   moveTo(0f,size.height*.76f)
   cubicTo(size.width*.14f,size.height*.68f,size.width*.18f,size.height*.3f,size.width*.32f,size.height*.48f)
   cubicTo(size.width*.46f,size.height*.68f,size.width*.55f,size.height*.22f,size.width*.68f,size.height*.35f)
   cubicTo(size.width*.82f,size.height*.48f,size.width*.88f,size.height*.12f,size.width,size.height*.18f)
  }
  drawPath(p,Green.copy(alpha=.18f),style=androidx.compose.ui.graphics.drawscope.Stroke(width=8.dp.toPx()))
  drawPath(p,Green,style=androidx.compose.ui.graphics.drawscope.Stroke(width=2.dp.toPx()))
  val x=size.width*phase
  drawCircle(Blue,radius=4.dp.toPx(),center=androidx.compose.ui.geometry.Offset(x,size.height*(.72f-.48f*phase)))
 }
}
@Composable private fun EquityChart(){ WalletSparkline() }
