// ============================================================
// Jira DC ScriptRunner — OpexAI LLM Pipeline Endpoint
// POST /rest/scriptrunner/latest/custom/opexai-flow
//
// Request  → { "question": "...", "chat_history": [ {inputs:{question:""}, outputs:{llm_output:""}} ] }
// Response → { "answer": "...", "complexity": "M", "isDone": true, "args": {...}, "trace": [] }
//
// LLM BACKEND: OpenAI-compatible local servis
// Ortam değişkenleri (Jira setenv.sh veya JVM args):
//   LLM_BASE_URL  = http://localhost:8000/v1        (zorunlu)
//   LLM_API_KEY   = dummy                           (gerekirse)
//   LLM_MODEL     = llama3                          (varsayılan: llama3)
// ============================================================

import groovy.json.JsonOutput
import groovy.json.JsonSlurper
import com.onresolve.scriptrunner.runner.rest.common.CustomEndpointProvider
import javax.ws.rs.*
import javax.ws.rs.core.*
import groovy.transform.Field

@BaseScript(com.onresolve.scriptrunner.runner.rest.common.CustomEndpointProvider)
script

// ============================================================
// SYSTEM PROMPTS  (birebir Python projesinden alınmıştır)
// ============================================================

@Field static final String ANALYST_SYSTEM_PROMPT = '''
Kullanıcılardan fikir, ihtiyaç ve gereksinimleri sistematik, analitik ve yönlendirici bir yaklaşımla toplayan bir analist asistansın.

Bir analist gibi davranırsın:
- Kullanıcının verdiği cevapları yüzeysel olarak kabul etmezsin.
- Gerektiğinde derinleştirir, açıklama ister, örneklerle yönlendirirsin.
- Kullanıcının cevabı muğlak, eksik, genel veya belirsizse bunu nazikçe belirtir ve detay isteyerek netleştirirsin.
- Asıl hedefin: Kullanıcıyı yormadan ama derinleştirerek, yüksek kaliteli bir fikir formu oluşturmaktır.

GENEL DAVRANIŞ KURALLARI:
- Her adımda yalnızca bir soru sor.
- Empatik, sade ve açıklayıcı bir üslup kullan.
- Cevabı sadece almakla yetinme; analiz et, gerekirse netlik sor.
- Her sorudan sonra kısa bir örnek ver.
- Cevapta başka alanlara ait bilgiler varsa bunları otomatik olarak ilgili alana yerleştir ve o soruyu tekrar sorma.
- Kullanıcı cevaplarını düzenli, profesyonel ve anlaşılır cümlelere dönüştür.
- Kullanıcı "fikrim yok", "vazgeçtim" vb. gibi süreci durdurursa süreci kibarca bitir ve function_call üretme.
- Süreç boyunca kullanıcıya cevap verirken JSON veya function_call kullanma; sadece doğal metinle konuş.
- Tüm alanlar dolunca önce profesyonel bir özet göster, ardından onay iste.
- Onay gelirse function_call üret.

TOPLANACAK ALANLAR (8Fikir Girişi ile uyumlu):

1. problem → "Bu fikir ile hangi problemi çözmeyi hedefliyorsunuz?"
   - Kullanıcıdan net bir problem cümlesi iste.
   - Çok genel ise neden sorun olduğu, nerede ortaya çıktığı, kimleri etkilediği gibi detayları sor.

2. mevcut_durum → "Şu an bu ihtiyaç nasıl karşılanıyor?"
   - Varsa mevcut süreç, workaround, manuel çözüm veya hiç çözülmüyor durumu sor.

3. fikrin_ozeti → "Adı" — Fikrin kısa ve net adı.

4. amac → "Bu fikir hangi amaca hizmet ediyor?"
   Seçenekler (bunlar dışında seçenek üretme):
   - Özel bankacılıkta karlı büyüme
   - Ticari bankacılıkta karlı büyüme
   - Tüzel mobilde işbirlikleri yoluyla kazanımın artması ve müşteri aktifliğini artıracak yeni ürünlerin hayata geçmesi
   - Şubelerin hızını ve satış potansiyelini artıracak veriye dayalı operasyonel karar süreçlerinin otomatik hale getirilmesi
   - Operasyonel verimlilik için manuel olan süreçlerin teknoloji ile yeniden tasarlanması
   - Regülatif /Yasal
   - Müşteri Deneyimini İyileştirme/Memnuniyetini Artırmak

5. fikrin_aciklamasi → "Açıklaması" — Fikrin detaylı açıklaması (free text).

6. cozum_tipi → "Kabaca nasıl bir çözüm yapılmasını istiyorsunuz?"
   - Örnekler: yeni ekran, süreç sadeleştirme, otomasyon, entegrasyon vb.

7. kanallar → "Bu geliştirme hangi kanallarda kullanılacak?" (Seçimli)
   Eşleştirme kuralları:
   - "mobil", "app", "telefon uygulaması" → Mobil Bankacılık
   - "internet bankacılığı", "IB", "online" → İnternet Bankacılığı
   - "web", "site", "tarayıcı" → Web
   - "çağrı merkezi", "müşteri hizmetleri" → Çağrı Merkezi
   - "şube", "bankaya gidince" → Şube
   - "ATM", "kart takınca" → ATM
   - "IVR", "sesli yanıt" → IVR
   - "video görüşme" → Video Bankacılık
   - "servis", "entegrasyon" → Servis Bankacılığı

8. hedef_kitle → "Bu çözümün hedef kitlesi kimler?"
   Örnekler: Bireysel müşteriler, KOBİ ve ticari işletmeler, Kurumsal firmalar,
   Tarımsal işletmeler, Özel bankacılık müşterileri, Dijital bankacılık kullanıcıları, Diğer

9. kpi (opsiyonel) → "Bu fikir ile hangi metriklerde fark yaratmayı hedefliyorsun?"
   Örnekler: işlem süresi, müşteri memnuniyeti, maliyet azaltma, dönüşüm oranı, hata oranı

SORU SORMA STRATEJİSİ:
- Tek satırlık, muğlak cevaplarda nazikçe daha fazla detay iste.
- Her alanı işlerken analist gibi düşün: tutarsızlık, eksiklik, belirsizlik varsa sor.
- Kullanıcıyı boğmadan ama cevabın gerçekten işe yarar olmasını sağlayacak şekilde derinleştir.

TÜM ALANLAR TAMAMLANDIĞINDA:
- Profesyonel ve düzenli bir özet oluştur. Her alanı başlıklandır, kurumsal bir dille sun.
- Ardından şunu sor: "Onaylıyorsanız 'Evet' yazabilirsiniz, değişiklik yapmak istiyorsanız hangi alanı güncellemek istediğinizi belirtin."
- Kullanıcı "Evet" derse, hiçbir normal metin yazmadan, şu alanların tümünü içeren bir function_call üret:
  fikrin_ozeti, fikrin_aciklamasi, amac, problem, cozum_tipi, kanallar, mevcut_durum, hedef_kitle, kpi
- Kullanıcı bir alanı güncellemek isterse sadece o alanı tekrar sor. Sonra tekrar özet göster ve onay iste.
'''

@Field static final String SIZING_SYSTEM_PROMPT_TEMPLATE = '''
# system:
🎯 ROL VE BAĞLAM:
Sen bankacılık sektöründe uzmanlaşmış Kıdemli Teknik Analist ve Takım Liderisin.
Görevin, gelen talepleri analiz ederek geliştirici ekipler için en doğru efor büyüklüğünü (T-Shirt Size) belirlemektir.

TEMEL PRENSİBİN: "Eşitlik değil, Adalet."
(Bir metin değişikliği ile bir API entegrasyonu matematiksel olarak eşit puanlanamaz.)

---

📚 BÖLÜM 1: REFERANS ÖRNEKLER (BENCHMARK)

1. ÖRNEK (XS): "Müşteri iletişim ekranındaki 'Telefon' label'ı 'GSM' olarak değiştirilsin." → Karar: XS
2. ÖRNEK (S):  "Kredi başvuru formuna 'Referans Kodu' adında opsiyonel bir alan eklensin." → Karar: S
3. ÖRNEK (M):  "Müşteri adres bilgileri artık MERNİS servisinden otomatik sorgulanıp güncellensin." → Karar: M
4. ÖRNEK (L):  "Tüm mobil uygulamada kullanılan Login SDK\'sı v2.0\'dan v3.0\'a yükseltilsin." → Karar: L

---

🛑 BÖLÜM 2: GELİŞTİRME FİLTRESİ

🔴 DEVELOPMENT DEĞİL (EFOR YOK):
- Kod/DB değişikliği gerektirmeyen konfigürasyonlar
- Data patch / Data fix scriptleri (tek seferlik)
- Yetki tanımları

🟢 DEVELOPMENT (EFOR VAR):
- Her türlü kod değişikliği, SDK/library güncellemeleri, güvenlik yamaları

---

🧮 BÖLÜM 3: AĞIRLIKLI PUANLAMA MOTORU

A. İş Akışı Netliği (Katsayı: 0.5)
   1=Çok Net / 3=Analiz Gerekli / 5=Çok Belirsiz

B. Etkilenen Sistem Sayısı (Katsayı: 1.5)
   1=Tek Sistem / 3=2-3 Sistem / 5=4+ Sistem veya Core Banking

C. Ekip Koordinasyonu (Katsayı: 1.0)
   1=Tek Ekip / 3=2-3 Ekip / 5=4+ Ekip

D. Geliştirme Derinliği (Katsayı: 2.5) — EN KRİTİK MADDE
   1=UI/Metin/Kozmetik / 2=Basit DB/Küçük Kural / 3=Yeni API/SDK Minor /
   4=Yeni Ekran/Karmaşık Akış / 5=Mimari Değişiklik/Refactoring/Yeni Entegrasyon

E. Test ve İş Birimi Etkisi (Katsayı: 1.0)
   1=Sadece IT / 3=2-3 Birim / 5=Tüm Banka

FORMÜL: (A×0.5) + (B×1.5) + (C×1.0) + (D×2.5) + (E×1.0)

---

🛡️ BÖLÜM 4: VETO VE GÜVENLİK KURALLARI

1. TEKNİK RİSK: SDK Upgrade / Framework Geçişi / Refactoring → Minimum Size: M
2. BÜYÜK İŞ: (Etkilenen Sistem ≥ 3) VE (Derinlik ≥ 4) → Direkt Size: L
3. XS KORUMASI: Geliştirme Derinliği > 1 → ASLA XS verme (Minimum S)

---

👕 BÖLÜM 5: BEDEN TABLOSU

 6.5 - 11.0 Puan → XS
11.5 - 18.0 Puan → S
18.5 - 26.0 Puan → M
26.5 - 32.5 Puan → L

---

Talep Bilgileri:
{{IDEA_JSON}}

📝 ÇIKTI FORMATI: Aşağıdaki alanları doldurarak score_complexity fonksiyonunu çağır (maks. 1000 karakter).

# user:
Talep Bilgileri:
{{IDEA_JSON}}

Yukarıdaki kurallara göre talebi değerlendir ve score_complexity fonksiyonunu çağır.
'''

// ============================================================
// TOOL DEFINITIONS  (OpenAI /v1/chat/completions formatı)
// ============================================================

@Field static final Map SUBMIT_IDEA_FORM_TOOL = [
    type    : "function",
    function: [
        name       : "submit_idea_form",
        description: "Formu submit eder. Tüm alanlar toplandıktan ve kullanıcı onayladıktan sonra çağrılır.",
        parameters : [
            type      : "object",
            properties: [
                fikrin_ozeti     : [type: "string", description: "Fikrin kısa ve net adı."],
                fikrin_aciklamasi: [type: "string", description: "Fikrin detaylı açıklaması."],
                amac             : [
                    type       : "string",
                    description: "Fikrin amaç kategorisi.",
                    "enum"     : [
                        "Özel bankacılıkta karlı büyüme",
                        "Ticari bankacılıkta karlı büyüme",
                        "Tüzel mobilde işbirlikleri yoluyla kazanımın artması ve müşteri aktifliğini artıracak yeni ürünlerin hayata geçmesi",
                        "Şubelerin hızını ve satış potansiyelini artıracak veriye dayalı operasyonel karar süreçlerinin otomatik hale getirilmesi",
                        "Operasyonel verimlilik için manuel olan süreçlerin teknoloji ile yeniden tasarlanması",
                        "Regülatif /Yasal",
                        "Müşteri Deneyimini İyileştirme/Memnuniyetini Artırmak"
                    ]
                ],
                problem          : [type: "string", description: "Hedeflenen problem tanımı."],
                cozum_tipi       : [type: "string", description: "Çözüm tipi veya yaklaşımı."],
                kanallar         : [
                    type       : "array",
                    description: "Geliştirmenin kullanılacağı kanallar.",
                    items      : [
                        type  : "string",
                        "enum": [
                            "Çağrı Merkezi", "İnternet Bankacılığı", "Mobil Bankacılık",
                            "Şube", "ATM", "Web", "Video Bankacılık", "IVR", "Servis Bankacılığı"
                        ]
                    ]
                ],
                mevcut_durum     : [type: "string", description: "İhtiyacın şu anki karşılanma durumu."],
                hedef_kitle      : [type: "string", description: "Hedef kitle tanımı."],
                kpi              : [type: "string", description: "Opsiyonel KPI veya metrik hedefleri."]
            ],
            required: [
                "fikrin_ozeti", "fikrin_aciklamasi", "amac", "problem",
                "cozum_tipi", "kanallar", "mevcut_durum", "hedef_kitle"
            ]
        ]
    ]
]

@Field static final Map SCORE_COMPLEXITY_TOOL = [
    type    : "function",
    function: [
        name       : "score_complexity",
        description: "Talebi efor büyüklüğüne göre puanlar.",
        parameters : [
            type      : "object",
            properties: [
                Talep_Tipi  : [
                    type       : "string",
                    description: "Talep tipini belirtir.",
                    "enum"     : ["Development", "Development Değil"]
                ],
                Analiz_Notu : [
                    type       : "string",
                    description: "Kısa gerekçe (maks. 150 karakter)."
                ],
                T_Shirt_Size: [
                    type       : "string",
                    description: "Belirlenen efor büyüklüğü.",
                    "enum"     : ["XS", "S", "M", "L"]
                ]
            ],
            required: ["Talep_Tipi", "Analiz_Notu", "T_Shirt_Size"]
        ]
    ]
]

// ============================================================
// PIPELINE STATE
// ============================================================

class PipelineState {
    // Konuşma geçmişi — [role: "user"|"assistant"|"tool_result", content: "..."]
    List    messages        = []

    // submit_idea_form çıktısı
    Map     idea_form       = null
    boolean form_submitted  = false

    // score_complexity çıktısı
    String  talep_tipi      = null
    String  t_shirt_size    = null
    String  analiz_notu     = null

    // Node içi routing için son tool call listesi (kalıcı değil)
    List    last_tool_calls = []
}

// ============================================================
// ENDPOINT
//
// REQUEST:
// {
//   "question": "Kullanıcının son mesajı",
//   "chat_history": [
//     {
//       "inputs":  { "question": "önceki kullanıcı mesajı" },
//       "outputs": { "llm_output": "önceki asistan cevabı" }
//     }
//   ]
// }
//
// RESPONSE:
// {
//   "answer":     "Kullanıcıya gösterilecek metin",
//   "complexity": "M",       // null | "XS" | "S" | "M" | "L"
//   "isDone":     true,      // submit_idea_form tamamlandıysa true
//   "args": {                // isDone=true ise dolu, aksi hâlde null
//     "fikrin_ozeti": "...",
//     "fikrin_aciklamasi": "...",
//     "amac": "...",
//     "problem": "...",
//     "cozum_tipi": "...",
//     "kanallar": ["..."],
//     "mevcut_durum": "...",
//     "hedef_kitle": "...",
//     "kpi": "..."
//   },
//   "trace": []              // ileride kullanım için rezerve
// }
// ============================================================

@POST
@Path("opexai-flow")
@Consumes(MediaType.APPLICATION_JSON)
@Produces(MediaType.APPLICATION_JSON)
Response opexaiFlow(String body) {

    def slurper = new JsonSlurper()
    Map request

    try {
        request = slurper.parseText(body) as Map
    } catch (Exception e) {
        return errorResponse(400, "Geçersiz JSON: ${e.message}")
    }

    // State'i chat_history'den inşa et
    PipelineState state = buildInitialState(request)

    // Pipeline'ı çalıştır
    try {
        runPipeline(state)
    } catch (Exception e) {
        return errorResponse(500, "Pipeline hatası: ${e.message}")
    }

    // Son assistant mesajını bul
    String answer = state.messages.reverse().find { it.role == "assistant" }?.content ?: ""

    Map responsePayload = [
        answer    : answer,
        complexity: state.t_shirt_size,
        isDone    : state.form_submitted,
        args      : state.idea_form,
        trace     : []
    ]

    return Response.ok(JsonOutput.toJson(responsePayload))
                   .header("Content-Type", "application/json; charset=UTF-8")
                   .build()
}

// ============================================================
// STATE BUILDER
// chat_history → messages listesine, yeni question → sona eklenir
// ============================================================

PipelineState buildInitialState(Map request) {
    PipelineState state = new PipelineState()

    String question    = (request.question     ?: "").toString().trim()
    List   chatHistory = (request.chat_history ?: []) as List

    chatHistory.each { item ->
        if (!(item instanceof Map)) return
        String prevQ = item?.inputs?.question?.toString()?.trim()   ?: ""
        String prevA = item?.outputs?.llm_output?.toString()?.trim() ?: ""
        if (prevQ) state.messages << [role: "user",      content: prevQ]
        if (prevA) state.messages << [role: "assistant", content: prevA]
    }

    if (question) {
        state.messages << [role: "user", content: question]
    }

    return state
}

// ============================================================
// PIPELINE  analyst → submit_tool → sizing → score_tool → finalize
// ============================================================

void runPipeline(PipelineState state) {
    runAnalystNode(state)

    if (hasToolCall(state, "submit_idea_form")) {
        runSubmitToolNode(state)
        runSizingNode(state)

        if (hasToolCall(state, "score_complexity")) {
            runScoreToolNode(state)
        }
    }

    runFinalizeNode(state)
}

// ============================================================
// NODE: analyst_llm
// ============================================================

void runAnalystNode(PipelineState state) {
    // Geçmişten sadece user/assistant mesajlarını al
    List llmMessages = state.messages
        .findAll { it.role in ["user", "assistant"] }
        .collect  { [role: it.role, content: it.content] }

    Map llmResponse = callLLM(
        systemPrompt: ANALYST_SYSTEM_PROMPT,
        messages    : llmMessages,
        tools       : [SUBMIT_IDEA_FORM_TOOL]
    )

    state.last_tool_calls = extractToolCalls(llmResponse)

    if (hasToolCall(state, "submit_idea_form")) {
        // Tool call üretildi; tool_result mesajını geçmişe ekle
        state.messages << [role: "tool_result", content: "Form başarıyla alındı."]
    } else {
        // Normal konuşma cevabı
        String textReply = extractText(llmResponse)
        state.messages << [role: "assistant", content: textReply]
    }
}

// ============================================================
// NODE: submit_tool_node
// ============================================================

void runSubmitToolNode(PipelineState state) {
    Map toolArgs = extractToolArgs(state.last_tool_calls, "submit_idea_form")
    if (toolArgs) {
        state.idea_form    = toolArgs
        state.form_submitted = true
    }
}

// ============================================================
// NODE: sizing_llm
// Sizing LLM fresh bir konuşmayla çalışır — sadece idea_form'u görür
// ============================================================

void runSizingNode(PipelineState state) {
    String ideaJson    = JsonOutput.toJson(state.idea_form)
    String sysPrompt   = SIZING_SYSTEM_PROMPT_TEMPLATE.replace("{{IDEA_JSON}}", ideaJson)

    List llmMessages = [[
        role   : "user",
        content: "Talep Bilgileri:\n${ideaJson}\n\nYukarıdaki kurallara göre talebi değerlendir ve score_complexity fonksiyonunu çağır."
    ]]

    Map llmResponse = callLLM(
        systemPrompt: sysPrompt,
        messages    : llmMessages,
        tools       : [SCORE_COMPLEXITY_TOOL]
    )

    state.last_tool_calls = extractToolCalls(llmResponse)
}

// ============================================================
// NODE: score_tool_node
// ============================================================

void runScoreToolNode(PipelineState state) {
    Map toolArgs = extractToolArgs(state.last_tool_calls, "score_complexity")
    if (toolArgs) {
        state.talep_tipi   = toolArgs.Talep_Tipi   ?: null
        state.t_shirt_size = toolArgs.T_Shirt_Size ?: null
        state.analiz_notu  = toolArgs.Analiz_Notu  ?: null
    }
}

// ============================================================
// NODE: finalize
// ============================================================

void runFinalizeNode(PipelineState state) {
    if (state.t_shirt_size) {
        String finalAnswer =
            "Fikriniz başarılı ile oluşturulmuştur.\n" +
            "Tahmini kompleksite değeri ${state.t_shirt_size} olarak belirlenmiştir.\n" +
            "Analiz Notu: ${state.analiz_notu ?: 'Analiz notu bulunamadı.'}\n" +
            "Sürecinizin devam etmesi için, 'Fikirlerim' sekmesi altından, " +
            "oluşturduğunuz fikrin olgunlaştırmasını sağlamanız gerekmektedir."

        state.messages << [role: "assistant", content: finalAnswer]
    }
    // Eğer scoring yoksa analyst'in son cevabı zaten messages'tadır.
}

// ============================================================
// OpenAI-COMPATIBLE LOCAL LLM API
//
// OpenAI /v1/chat/completions formatı kullanılır.
// Tool call request  → tools[] + tool_choice: "auto"
// Tool call response → choices[0].message.tool_calls[].function.{name, arguments}
// Normal response    → choices[0].message.content
// ============================================================

Map callLLM(Map params) {

    // --- Konfigürasyon (ortam değişkenlerinden) ---
    String baseUrl = (System.getenv("LLM_BASE_URL") ?: "http://localhost:8000/v1").replaceAll("/\$", "")
    String apiKey  =  System.getenv("LLM_API_KEY")  ?: "dummy"
    String model   =  System.getenv("LLM_MODEL")    ?: "llama3"

    // --- Mesaj listesini oluştur ---
    // OpenAI formatı: system mesajı messages[0] olarak eklenir
    List openAiMessages = []

    if (params.systemPrompt) {
        openAiMessages << [role: "system", content: params.systemPrompt]
    }

    // tool_result → OpenAI'da role: "tool" olarak gönderilir
    (params.messages as List).each { msg ->
        if (msg.role == "tool_result") {
            openAiMessages << [
                role        : "tool",
                tool_call_id: msg.tool_call_id ?: "call_0",
                content     : msg.content?.toString() ?: ""
            ]
        } else {
            openAiMessages << [role: msg.role, content: msg.content]
        }
    }

    // --- Request body ---
    Map requestBody = [
        model      : model,
        max_tokens : 2048,
        temperature: 0,
        messages   : openAiMessages
    ]

    if (params.tools) {
        requestBody.tools       = params.tools
        requestBody.tool_choice = "auto"
    }

    String requestJson = JsonOutput.toJson(requestBody)

    // --- HTTP isteği ---
    URL               url  = new URL("${baseUrl}/chat/completions")
    HttpURLConnection conn = (HttpURLConnection) url.openConnection()
    conn.setRequestMethod("POST")
    conn.setDoOutput(true)
    conn.setRequestProperty("Content-Type",  "application/json; charset=UTF-8")
    conn.setRequestProperty("Authorization", "Bearer ${apiKey}")
    conn.setConnectTimeout(30_000)
    conn.setReadTimeout(90_000)

    conn.outputStream.withWriter("UTF-8") { writer -> writer.write(requestJson) }

    int         statusCode   = conn.responseCode
    InputStream stream       = statusCode < 400 ? conn.inputStream : conn.errorStream
    String      responseText = stream.getText("UTF-8")

    if (statusCode >= 400) {
        throw new RuntimeException("LLM API hatası [HTTP ${statusCode}]: ${responseText}")
    }

    return new JsonSlurper().parseText(responseText) as Map
}

// ============================================================
// HELPERS
// ============================================================

// OpenAI response → tool call listesi
// choices[0].message.tool_calls[].function.{name, arguments}
List extractToolCalls(Map llmResponse) {
    List choices = llmResponse?.choices ?: []
    if (!choices) return []

    Map message   = choices[0]?.message as Map ?: [:]
    List toolCalls = message?.tool_calls as List ?: []

    return toolCalls.collect { tc ->
        Map fn   = tc?.function as Map ?: [:]
        def args = fn?.arguments

        // arguments string olarak gelebilir — parse et
        if (args instanceof String) {
            try { args = new JsonSlurper().parseText(args) } catch (Exception ignored) { args = [:] }
        }

        [
            name: fn?.name ?: "",
            args: args instanceof Map ? args : [:],
            id  : tc?.id   ?: (fn?.name ?: "call_0")
        ]
    }
}

boolean hasToolCall(PipelineState state, String toolName) {
    return state.last_tool_calls.any { it.name == toolName }
}

Map extractToolArgs(List toolCalls, String toolName) {
    return toolCalls.find { it.name == toolName }?.args as Map ?: null
}

// OpenAI response → düz metin
// choices[0].message.content
String extractText(Map llmResponse) {
    List choices = llmResponse?.choices ?: []
    if (!choices) return ""
    return choices[0]?.message?.content?.toString()?.trim() ?: ""
}

Response errorResponse(int status, String message) {
    return Response.status(status)
                   .entity(JsonOutput.toJson([error: message]))
                   .header("Content-Type", "application/json; charset=UTF-8")
                   .build()
}
