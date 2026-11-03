package com.diomaster2d.grokbot

import android.os.Bundle
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
private val Red = Color(0xFFFF4058)
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
}

@Composable private fun App(){
 var gateway by remember { mutableStateOf("") }; var seat by remember { mutableStateOf("risk") }; var token by remember { mutableStateOf("") }
 var tools by remember { mutableStateOf(emptyList<DeskTool>()) }; var client by remember { mutableStateOf<DeskClient?>(null) }
 var status by remember { mutableStateOf("OFFLINE · PAPER MODE") }; var message by remember { mutableStateOf("Σύνδεσε το Desk Gateway για ζωντανά δεδομένα.") }
 var busy by remember { mutableStateOf(false) }; var tab by remember { mutableIntStateOf(0) }
 var equity by remember { mutableStateOf("--") }; var pnl by remember { mutableStateOf("--") }; var cash by remember { mutableStateOf("--") }
 var activity by remember { mutableStateOf(emptyList<String>()) }
 val scope= rememberCoroutineScope()
 fun run(block:suspend()->Unit){scope.launch{busy=true;try{block()}catch(e:Exception){message=e.message?: "Σφάλμα σύνδεσης";status="DISCONNECTED"}finally{busy=false}}}
 val tabs=listOf("Home","Scanner","Agents","Trades","Portfolio","Rules")
 Scaffold(containerColor=Bg,bottomBar={NavigationBar(containerColor=Color(0xFF101219),contentColor=Color.White){
  tabs.forEachIndexed { i,s -> NavigationBarItem(selected=tab==i,onClick={tab=i},icon={Text(listOf("⌂","⌕","✣","⇄","▣","⬡")[i],fontSize=20.sp)},label={Text(s,fontSize=10.sp)},colors=NavigationBarItemDefaults.colors(selectedIconColor=Red,indicatorColor=Color(0xFF35202A),selectedTextColor=Color.White,unselectedTextColor=Muted)) }
 }}) { pad ->
  LazyColumn(Modifier.fillMaxSize().padding(pad).background(Bg).padding(horizontal=16.dp),verticalArrangement=Arrangement.spacedBy(13.dp),contentPadding=PaddingValues(top=18.dp,bottom=24.dp)){
   item { Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween,verticalAlignment=Alignment.CenterVertically){
    Column { Text("DioMasteR2D Grokbot Trade",fontSize=20.sp,fontWeight=FontWeight.Bold);Text("SOLANA · PAPER TRADING DESK",fontSize=10.sp,color=Muted,letterSpacing=2.sp) }
    Column(horizontalAlignment=Alignment.End){Text("●  "+status,fontSize=10.sp,color=if(status.startsWith("CONNECTED")) Green else Red);Text("PAPER ONLY",fontSize=10.sp,color=Green)}
   }}
   when(tab){
    0 -> {
     item { CardBox { Column {
      Text("PAPER PORTFOLIO",fontSize=11.sp,color=Muted,letterSpacing=1.5.sp)
      Text(equity,fontSize=36.sp,fontWeight=FontWeight.Bold,color=Color.White)
      Text("Equity · live data appears after gateway connection",fontSize=11.sp,color=Muted)
      Spacer(Modifier.height(10.dp));Row(horizontalArrangement=Arrangement.spacedBy(18.dp)){Metric("P&L",pnl,Green);Metric("CASH",cash,Color.White)}
      Spacer(Modifier.height(12.dp));EquityChart()
      Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween){Text("LIVE",color=Green,fontSize=12.sp,fontWeight=FontWeight.Bold);Text("1H     4H     1D     1W     ALL",color=Green,fontSize=11.sp)}
     }}
     }
     item { Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween){Text("AGENT NETWORK",fontSize=18.sp,fontWeight=FontWeight.Bold);Text("${tools.size} TOOLS",fontSize=11.sp,color=Green)} }
     item { Row(horizontalArrangement=Arrangement.spacedBy(9.dp)){AgentCard("SCANNER","Token discovery","SCOUT",Color(0xFF26D6C5));AgentCard("ANALYST","Signal review","SIGNAL",Red);AgentCard("RISK GUARD","Risk veto","RISK",Green)} }
     item { Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween){Text("RECENT ACTIVITY",fontSize=18.sp,fontWeight=FontWeight.Bold);Text("LEDGER",fontSize=10.sp,color=Green)} }
     if(activity.isEmpty()) item { CardBox { Text(message,fontSize=12.sp,color=Muted) } } else items(activity.take(12)){line->CardBox{Text(line,fontSize=12.sp,color=Color.White)}}
    }
    1 -> {
     item { Text("AGENTS & TOOLS",fontSize=20.sp,fontWeight=FontWeight.Bold) }
     if(tools.isEmpty()) item { CardBox { Text("Δεν έχουν φορτωθεί εργαλεία. Συνδέσου πρώτα στο gateway.",color=Muted) } }
     items(tools){t->CardBox{Column(verticalArrangement=Arrangement.spacedBy(5.dp)){Text(t.name,color=Green,fontWeight=FontWeight.Bold);Text(t.description,color=Muted,fontSize=12.sp)}}}
    }
    2 -> {
     item { Text("ACTIVITY & LEDGER",fontSize=20.sp,fontWeight=FontWeight.Bold) }
     if(activity.isEmpty()) item { CardBox { Text("Δεν υπάρχουν δεδομένα ledger μέχρι να συνδεθεί ο server.",color=Muted) } }
     items(activity){line->CardBox{Text(line,fontSize=12.sp)}}
    }
    else -> {
     item { Text("DESK CONNECTION",fontSize=20.sp,fontWeight=FontWeight.Bold) }
     item { CardBox { Column(verticalArrangement=Arrangement.spacedBy(10.dp)){
      Text("Gateway HTTPS URL",color=Muted,fontSize=12.sp);OutlinedTextField(gateway,{gateway=it},modifier=Modifier.fillMaxWidth(),singleLine=true,placeholder={Text("https://your-secure-gateway")})
      Text("Seat",color=Muted,fontSize=12.sp);OutlinedTextField(seat,{seat=it.trim().lowercase()},modifier=Modifier.fillMaxWidth(),singleLine=true)
      Text("Bearer token",color=Muted,fontSize=12.sp);OutlinedTextField(token,{token=it},modifier=Modifier.fillMaxWidth(),singleLine=true,visualTransformation=PasswordVisualTransformation())
      Button(onClick={run{
       require(gateway.startsWith("https://")){"Χρειάζεται ασφαλής HTTPS διεύθυνση gateway."}
       val c=DeskClient(gateway.trim().removeSuffix("/"),seat.trim(),token.trim());val found=c.connect()
       client=c;tools=found;status="CONNECTED · PAPER";message="Συνδέθηκε. Φορτώθηκαν ${found.size} εργαλεία."
       val exp=runCatching{c.call("portfolio_exposure")}.getOrNull()
       val pn=runCatching{c.call("portfolio_pnl",JSONObject().put("window","day"))}.getOrNull()
       val led=runCatching{c.call("portfolio_ledger_read",JSONObject().put("limit",20))}.getOrNull()
       if(exp!=null){equity=exp.toString();cash="paper"}
       if(pn!=null)pnl=pn.toString()
       if(led!=null)activity=listOf(led.toString())
      }},enabled=!busy&&gateway.isNotBlank()&&token.isNotBlank(),modifier=Modifier.fillMaxWidth(),colors=ButtonDefaults.buttonColors(containerColor=Red)){Text(if(busy)"CONNECTING..." else "CONNECT DESK")}
      Text(message,fontSize=11.sp,color=Muted)
      Text("Το token μένει μόνο στη μνήμη της εφαρμογής. Μην βάλεις seed phrase ή private key.",fontSize=11.sp,color=Green)
     }}}
     item { CardBox { Text("Live trading απενεργοποιημένο. Η εφαρμογή χρησιμοποιεί μόνο paper tools που εκθέτει ο server.",color=Red,fontSize=12.sp) } }
    }
   }
  }
 }
}
@Composable private fun CardBox(content:@Composable ColumnScope.()->Unit){Card(colors=CardDefaults.cardColors(containerColor=Panel),shape=RoundedCornerShape(18.dp),modifier=Modifier.fillMaxWidth()){Column(Modifier.padding(16.dp),content=content)}}
@Composable private fun Metric(label:String,value:String,color:Color){Column{Text(label,fontSize=10.sp,color=Muted);Text(value,fontSize=17.sp,fontWeight=FontWeight.Bold,color=color)}}
@Composable private fun AgentCard(name:String,desc:String,id:String,color:Color){Card(Modifier.width(155.dp),colors=CardDefaults.cardColors(containerColor=Panel),shape=RoundedCornerShape(16.dp)){Column(Modifier.padding(14.dp)){Text("✦",fontSize=24.sp,color=color);Text(name,fontWeight=FontWeight.Bold);Text(desc,fontSize=10.sp,color=Muted);Text("AGENT $id",fontSize=9.sp,color=color)}}}
@Composable private fun EquityChart(){
 Canvas(Modifier.fillMaxWidth().height(125.dp)){val p=Path().apply{moveTo(0f,size.height*.83f);cubicTo(size.width*.18f,size.height*.84f,size.width*.2f,size.height*.45f,size.width*.36f,size.height*.58f);cubicTo(size.width*.5f,size.height*.7f,size.width*.55f,size.height*.3f,size.width*.7f,size.height*.4f);cubicTo(size.width*.82f,size.height*.5f,size.width*.88f,size.height*.12f,size.width,size.height*.2f)};drawPath(p,Green,style=androidx.compose.ui.graphics.drawscope.Stroke(width=3.dp.toPx()));}
}
