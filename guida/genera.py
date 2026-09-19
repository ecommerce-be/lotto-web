"""Genera la guida di App Lotto in PDF."""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (ListFlowable, ListItem, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

ACCENTO = colors.HexColor("#8a5a2b")
TESTO = colors.HexColor("#1a1a19")
TENUE = colors.HexColor("#6b6a66")
BORDO = colors.HexColor("#e3e1dc")
SFONDO = colors.HexColor("#faf9f7")
ROSSO = colors.HexColor("#a33a2e")

base = getSampleStyleSheet()
S = {
    "titolo": ParagraphStyle("titolo", parent=base["Title"], fontName="Helvetica-Bold",
                             fontSize=25, leading=29, textColor=TESTO, alignment=0,
                             spaceAfter=4),
    "sottotitolo": ParagraphStyle("sottotitolo", parent=base["Normal"],
                                  fontName="Helvetica", fontSize=11.5, leading=16,
                                  textColor=TENUE, spaceAfter=20),
    "h1": ParagraphStyle("h1", parent=base["Heading1"], fontName="Helvetica-Bold",
                         fontSize=15, leading=19, textColor=ACCENTO,
                         spaceBefore=18, spaceAfter=7),
    "h2": ParagraphStyle("h2", parent=base["Heading2"], fontName="Helvetica-Bold",
                         fontSize=11.5, leading=15, textColor=TESTO,
                         spaceBefore=12, spaceAfter=4),
    "p": ParagraphStyle("p", parent=base["Normal"], fontName="Helvetica",
                        fontSize=10.2, leading=14.9, textColor=TESTO,
                        alignment=TA_JUSTIFY, spaceAfter=8),
    "lista": ParagraphStyle("lista", parent=base["Normal"], fontName="Helvetica",
                            fontSize=10.3, leading=15, textColor=TESTO, spaceAfter=5),
    "riquadro": ParagraphStyle("riquadro", parent=base["Normal"], fontName="Helvetica",
                               fontSize=10, leading=15, textColor=TESTO,
                               alignment=TA_JUSTIFY,
                               leftIndent=10, rightIndent=10,
                               spaceBefore=9, spaceAfter=9),
    "cella": ParagraphStyle("cella", parent=base["Normal"], fontName="Helvetica",
                            fontSize=9, leading=12.4, textColor=TESTO),
    "cella_t": ParagraphStyle("cella_t", parent=base["Normal"], fontName="Helvetica-Bold",
                              fontSize=8.2, leading=11, textColor=TENUE),
    "piede": ParagraphStyle("piede", parent=base["Normal"], fontName="Helvetica-Oblique",
                            fontSize=8.8, leading=12.4, textColor=TENUE),
}


def P(testo, stile="p"):
    return Paragraph(testo, S[stile])


def punti(voci):
    return ListFlowable(
        [ListItem(P(v, "lista"), leftIndent=14, value="circle") for v in voci],
        bulletType="bullet", bulletFontSize=5, bulletColor=ACCENTO,
        leftIndent=12, spaceAfter=9)


def riquadro(righe):
    """Un blocco evidenziato, con la barretta color accento a sinistra."""
    t = Table([[Paragraph(r, S["riquadro"])] for r in righe], colWidths=[16.4 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), SFONDO),
        ("LINEBEFORE", (0, 0), (0, -1), 2.2, ACCENTO),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return t


def tabella(intestazioni, righe, larghezze):
    dati = [[Paragraph(h, S["cella_t"]) for h in intestazioni]]
    dati += [[Paragraph(c, S["cella"]) for c in r] for r in righe]
    t = Table(dati, colWidths=larghezze, repeatRows=1)
    t.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, ACCENTO),
        ("LINEBELOW", (0, 1), (-1, -2), 0.4, BORDO),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def intestazione_pagina(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(TENUE)
    if doc.page > 1:
        canvas.drawString(2.3 * cm, A4[1] - 1.3 * cm, "App Lotto — guida")
    canvas.drawRightString(A4[0] - 2.3 * cm, 1.3 * cm, str(doc.page))
    canvas.restoreState()


storia = []
A = storia.append

# ---------------------------------------------------------------- copertina
A(P("App Lotto", "titolo"))
A(P("Guida all’uso — i sei metodi dei tuoi fascicoli, applicati da soli "
    "a ogni estrazione.<br/>Settembre 2026", "sottotitolo"))

A(riquadro([
    "<b>L’indirizzo del sito:</b> ecommerce-be.github.io/lotto-web",
    "Si apre dal telefono, dal tablet o dal computer. Non c’è niente da "
    "installare e non serve nessuna password.",
]))

A(P("Questa guida spiega che cosa fa il sito, come si leggono le sue quattro "
    "pagine, che cosa fa con i metodi dei fascicoli, e — la parte più "
    "importante — che cosa è in grado di fare e che cosa no."))

# ---------------------------------------------------------------- 1
A(P("Che cos’è", "h1"))
A(P("È un sito che fa automaticamente il lavoro che finora si faceva a mano "
    "sui fascicoli: ogni volta che esce un’estrazione, controlla tutte e dieci "
    "le ruote e tutte le loro combinazioni per vedere se si presenta una delle "
    "configurazioni descritte nei sei metodi. Quando ne trova una, calcola i numeri "
    "da giocare, si ricorda per quanti colpi valgono, e nei giorni successivi "
    "controlla da solo se sono usciti."))
A(P("Non inventa niente e non aggiunge niente di suo: applica le regole dei "
    "fascicoli alla lettera. Il vantaggio non è che “azzecca di più”, "
    "ma che non sbaglia un conto, non salta un’estrazione, non si dimentica "
    "di controllare una previsione di dieci giorni fa, e tiene il conto onesto "
    "di come è andata."))

A(P("Da dove prende i numeri", "h2"))
A(P("Le estrazioni arrivano dal sito ufficiale del Lotto. L’archivio storico "
    "parte dal 1939 e contiene oggi <b>7.382 concorsi</b>. I numeri sono "
    "conservati <b>nell’ordine in cui sono stati estratti</b>, non riordinati "
    "dal più piccolo al più grande: è un dettaglio che sembra da nulla "
    "e invece è decisivo, perché quattro metodi su sei guardano la "
    "<i>posizione</i> di un numero nella cinquina. Su un archivio riordinato quei "
    "metodi continuerebbero a funzionare misurando però tutt’altra cosa, "
    "senza che nessuno se ne accorga."))

A(P("Quando si aggiorna", "h2"))
A(P("Da solo, ogni sera, un’ora dopo l’estrazione, e di nuovo il mattino "
    "dopo per sicurezza. Non serve accendere nessun computer: se ne occupa il "
    "servizio dove il sito è ospitato. In cima alla pagina c’è sempre "
    "scritto di che giorno è l’ultima estrazione caricata; se per qualche "
    "motivo restasse indietro di più di quattro giorni, compare un avviso "
    "rosso invece di far finta di niente."))
A(P("Il Lotto non si estrae tutti i giorni: al momento sono quattro estrazioni "
    "a settimana — martedì, giovedì, venerdì e sabato. Se apri il "
    "sito di domenica o di lunedì e l’ultima estrazione è di sabato, "
    "è tutto normale.", "piede"))

# ---------------------------------------------------------------- 2
A(P("Le cinque pagine", "h1"))
A(P("In alto ci sono cinque pulsanti: <b>Schedina</b>, <b>Previsioni</b>, "
    "<b>In corso</b>, <b>Bilancio</b>, <b>Estrazioni</b>. Sono cinque modi di "
    "guardare la stessa cosa."))

A(P("1. Schedina \u2014 che cosa giocare al prossimo concorso", "h2"))
A(P("\u00c8 la pagina che si apre per prima. In cima dice quand\u2019\u00e8 "
    "la prossima estrazione e quanto manca. Sotto scrivi quanto vuoi spendere, "
    "e il sito compone una giocata concreta: queste sorti, su queste ruote, due "
    "euro l\u2019una, con il costo totale, la probabilit\u00e0 di portare a "
    "casa qualcosa e quanto torna indietro in media."))
A(P("Le giocate sono in ordine di <b>rarit\u00e0 del metodo</b>: prima quelle "
    "che capitano poche volte l\u2019anno. A parit\u00e0 di metodo viene "
    "prima ci\u00f2 che scade (le giocate all\u2019ultimo colpo sono segnate), "
    "e prima la sorte che rende di pi\u00f9 \u2014 cos\u00ec, se il budget non "
    "basta per tutto, a restare fuori sono i terni e non gli ambi."))

A(riquadro([
    "<b>Sui numeri il sito non d\u00e0 nessun consiglio, e non \u00e8 una "
    "reticenza.</b> Nel Lotto le quote sono fissate per legge e la "
    "probabilit\u00e0 \u00e8 la stessa per qualunque combinazione: a "
    "parit\u00e0 di sorte il ritorno atteso di ogni giocata possibile \u00e8 "
    "identico. Mettere i numeri in classifica dal migliore al peggiore "
    "significherebbe inventare un ordine che non esiste. Le uniche scelte che "
    "cambiano davvero qualcosa sono quante giocate fare, su quante ruote, e "
    "per quale sorte \u2014 ed \u00e8 su quelle che la pagina lavora.",
]))

A(P("In fondo compaiono i numeri chiesti da pi\u00f9 previsioni insieme. Non "
    "li rende pi\u00f9 probabili: significa solo che coprendoli si soddisfano "
    "pi\u00f9 previsioni con meno giocate distinte, che \u00e8 un risparmio "
    "vero. E, chiusa, c\u2019\u00e8 la voce <i>\u201cPreferisci giocare "
    "numeri tuoi?\u201d</i>: apre la griglia dei novanta numeri per dare un "
    "prezzo a una giocata qualunque, anche una che non viene da nessun metodo."))

A(P("2. Previsioni \u2014 i numeri in comune, e i concorsi del passato", "h2"))
A(P("In cima alla pagina c\u2019\u00e8 un elenco che raccoglie i numeri chiesti <b>da pi\u00f9 di un metodo</b> nello "
    "stesso momento, e ne fa una <b>previsione unica</b>: i cinque pi\u00f9 "
    "richiesti, giocati per ambo sulla ruota su cui quel gruppo torna pi\u00f9 "
    "spesso. Per ogni numero dice da quanti metodi \u00e8 chiesto, da quante "
    "previsioni e su quali ruote."))
A(riquadro([
    "<b>Che due metodi indichino lo stesso numero non lo rende pi\u00f9 "
    "probabile.</b> Il Lotto non ha memoria: un ambo resta uno su 400,5 anche "
    "se lo indicano tutti e sei. Serve a un\u2019altra cosa \u2014 con "
    "dieci ambi si coprono parecchie previsioni vive invece di giocarle una "
    "per una.",
    "E c\u2019\u00e8 un secondo motivo per non leggerci un pronostico, ed \u00e8 "
    "spiegato pi\u00f9 avanti in questa guida: <b>i sei metodi non sono sei pareri "
    "indipendenti</b>. Le loro condizioni di ricerca si riducono a tre, quindi "
    "due metodi che ne condividono una vanno d\u2019accordo per costruzione, non "
    "perch\u00e9 si siano trovati d\u2019accordo. Per questo la pagina conta i "
    "<b>metodi</b> e non le previsioni: due previsioni dello stesso metodo non "
    "sono due pareri.",
]))

A(P("Sotto, <b>\u201cChe cosa avrebbero detto i metodi\u201d</b>. Si sceglie un "
    "concorso qualunque \u2014 anche del 1939, ci sono tutti \u2014 e una ruota, "
    "si preme <i>Guarda quel concorso</i>, e la pagina risponde tre cose in "
    "fila. I pulsanti <i>10 anni fa</i>, <i>20 anni fa</i> e gli altri portano "
    "indietro in un colpo solo; se il giorno scelto non era di concorso, il "
    "programma prende il pi\u00f9 vicino e lo dice."))
A(punti([
    "<b>I cinque numeri usciti</b> su quella ruota quel giorno.",
    "<b>Le previsioni che i sei metodi hanno rilevato</b>, con davanti quelle "
    "che toccano la ruota scelta. Ognuna dice com\u2019\u00e8 finita: dentro i "
    "colpi che il fascicolo prescrive, a che colpo e su quale ruota \u00e8 "
    "uscita, oppure <i>scaduta senza esito</i>. In quel caso, in fondo e in "
    "corsivo, c\u2019\u00e8 anche quando si sarebbe verificata <i>dopo</i> la "
    "scadenza \u2014 ma a giocata chiusa, quindi senza vincere niente.",
    "<b>I numeri derivati dai cinque</b>: complemento, diametrale, vertibile, "
    "terzina simmetrica, figura e cadenza, e su quali ruote sono usciti nei "
    "dodici concorsi successivi.",
]))
A(riquadro([
    "<b>Il terzo blocco non sono previsioni, ed \u00e8 scritto anche l\u00ec.</b> "
    "I sei metodi non partono da cinque numeri: partono da una condizione su "
    "tutto il concorso \u2014 due ambi con la stessa somma, quattro numeri della "
    "stessa figura, un ambo diametrale \u2014 e solo quando quella scatta dicono "
    "che cosa giocare. Applicare le loro formule a cinque numeri qualunque d\u00e0 "
    "sempre un risultato, per costruzione. Sono numeri derivati, e chiamarli "
    "previsione sarebbe l\u2019unica vera bugia che questo sito potrebbe dire.",
    "Su nove date-ruota su dieci una previsione vera c\u2019\u00e8. Quando non "
    "c\u2019\u00e8, la pagina lo dice: i metodi cercano una configurazione, non "
    "dei numeri, e quasi sempre quella configurazione non si presenta.",
]))

A(P("Pi\u00f9 in fondo, <b>\u201cL\u2019elenco di tutto\u201d</b>: ogni numero che i sei "
    "metodi hanno giocato, su ogni ruota, a ogni concorso, con com\u2019\u00e8 "
    "andata. Si sceglie un anno \u2014 sono sedicimila righe l\u2019anno, tutte "
    "insieme non starebbero in un telefono \u2014 e poi si restringe con le "
    "tendine: ruota, metodo, sorte, e <i>com\u2019\u00e8 andata</i>. La tabella si "
    "sfoglia cento righe per volta, e il tasto in fondo salva in un file per "
    "Excel <b>esattamente le righe rimaste</b>, cos\u00ec te le riordini come "
    "vuoi."))
A(P("Accanto all\u2019anno c\u2019\u00e8 il campo <b>Giorno</b>: se la data la sai gi\u00e0, "
    "mettila l\u00ec e vedi solo quel concorso invece di tutto l\u2019anno. Se la data "
    "\u00e8 di un altro anno, l\u2019anno cambia da solo; se quel giorno non si \u00e8 "
    "estratto, il programma prende il concorso pi\u00f9 vicino e te lo scrive. Il "
    "tasto <i>tutto l\u2019anno</i> riporta indietro."))
A(P("Nella colonna <i>com\u2019\u00e8 andata</i> ci sono quattro risposte, e "
    "vale la pena distinguerle:", "lista"))
A(punti([
    "<b>uscita</b> \u2014 su quella ruota, entro i colpi previsti. \u00c8 la riga "
    "che avrebbe pagato, e dice a che colpo.",
    "<b>sospesa</b> \u2014 i numeri non sono usciti su questa ruota, ma la "
    "giocata si era gi\u00e0 chiusa su un\u2019altra ruota della stessa previsione. "
    "Come dicono i fascicoli, quando la sorte si verifica si sospende: da l\u00ec "
    "in avanti non si gioca e non si spende, nemmeno sulle altre ruote. Dire "
    "\u201cscaduta\u201d sarebbe falso, e la riga dice dove e quando si \u00e8 chiusa.",
    "<b>scaduta</b> \u2014 i colpi sono finiti e non \u00e8 uscita da nessuna parte. "
    "Se qualche numero era uscito da solo, la riga lo segnala.",
    "<b>ancora in gioco</b> \u2014 i colpi non sono ancora finiti: si sapr\u00e0.",
]))

A(P("3. In corso \u2014 tutto quello che \u00e8 ancora in gioco", "h2"))
A(P("La stessa materia della Schedina, ma senza il filtro del budget: tutte le "
    "previsioni ancora valide, raggruppate per metodo. Ogni riquadro dice il "
    "giorno del rilevamento, su quali ruote si gioca, quanti colpi restano "
    "(\u201c8 colpi su 12\u201d vuol dire che ne sono gi\u00e0 passati "
    "quattro), e i numeri divisi per tipo di giocata. Se c\u2019\u00e8 "
    "scritto \u201canche a Tutte\u201d, il fascicolo prevede di poterla "
    "giocare su tutte le ruote, ma \u00e8 facoltativo."))
A(P("I gruppi pi\u00f9 affollati partono chiusi e si aprono con un tocco. "
    "Anche qui l\u2019ordine \u00e8 per rarit\u00e0: \u201cLotto Facile "
    "\u2014 Il Metodo Vincente\u201d produce pi\u00f9 di mille rilevamenti "
    "l\u2019anno e \u201cFulmine\u201d meno di cento, e ordinando per data "
    "il secondo finirebbe sepolto sotto il primo."))

A(P("4. Bilancio \u2014 quanto \u00e8 costato e quanto ha reso", "h2"))
A(P("\u00c8 la pagina scomoda, ed \u00e8 quella che rende questo sito diverso "
    "da un volantino. Per ogni metodo dice quante previsioni ha prodotto, "
    "quanto sarebbe costato giocarle tutte, quanto avrebbero fruttato alle "
    "quote ufficiali, e il saldo. Il conto segue le convenzioni dei fascicoli: "
    "un euro per ogni sorte, per ogni ruota, per ogni colpo, e la sorte si "
    "sospende quando si verifica. Le vincite sono al netto della ritenuta "
    "dell\u20198%."))
A(P("Dove c\u2019\u00e8 scritto <i>campione troppo piccolo per essere "
    "indicativo</i>, quel saldo non vuol dire niente: le previsioni sono troppo "
    "poche e un solo terno ne ribalta il segno. \u00c8 il caso, per esempio, di "
    "\u201cUn Solo Ambo Secco\u201d, che con quattro previsioni in tutto "
    "mostra un ritorno dell\u2019821% \u2014 un numero che non significa nulla."))

A(P("5. Estrazioni \u2014 che cosa \u00e8 uscito", "h2"))
A(P("Gli ultimi otto concorsi, con tutte e dieci le ruote, "
    "nell\u2019ordine di estrazione. Serve per un controllo veloce senza "
    "andare a cercare altrove."))

A(P("I sei metodi", "h1"))
A(P("Sono quelli dei fascicoli, applicati alla lettera. La colonna "
    "“Rilevamenti” dice quante volte l’anno ciascun metodo trova la "
    "sua configurazione: sono differenze enormi, ed è la ragione per cui la "
    "pagina “In corso” li ordina per rarità."))

A(tabella(
    ["Metodo", "Che cosa cerca", "Che cosa gioca", "Colpi", "Rilevamenti<br/>all’anno"],
    [
        ["<b>Lotto Facile</b><br/>Il Metodo Vincente",
         "Due ambi su due ruote, nella stessa posizione, con la stessa somma",
         "Ambata, due ambi, un terno", "5–6", "1.062"],
        ["<b>Lotto Facile 4</b><br/>Ciclo-Pondometria",
         "Due ambi della stessa terzina simmetrica, nella stessa posizione su due ruote",
         "Ambata, tre ambi, una terzina", "9–14", "155"],
        ["<b>Lotto Facile 5</b><br/>Rita Calone",
         "Un ambo diametrale su una ruota sola",
         "Due ambate, quattro ambi, quattro quartine", "9", "227"],
        ["<b>Fulmine</b><br/>Osvaldo Manara",
         "Quattro numeri della stessa figura o cadenza, come due ambi su due ruote",
         "Ambata, tre ambi, una quartina", "12", "89"],
        ["<b>Un Solo Ambo Secco</b>",
         "Sei numeri su due ruote, a distanza 30 e tutti della stessa tripla figurale",
         "Un solo ambo secco", "4", "4"],
        ["<b>Ambo Secco Caotico</b><br/>Antonio Longo",
         "Un numero ripetuto su due ruote, più il suo complemento a 90 su una terza",
         "Uno o due ambi secchi", "2", "642"],
    ],
    [3.5 * cm, 5.2 * cm, 4.1 * cm, 1.5 * cm, 2.1 * cm]))

A(Spacer(1, 10))
A(P("I colpi indicati sono quelli che prescrive ciascun fascicolo. I rilevamenti "
    "all’anno sono misurati sui dati veri dell’ultimo anno, non stimati.",
    "piede"))

A(P("Una cosa che è emersa studiandoli", "h2"))
A(P("Mettendo i sei metodi uno accanto all’altro, si scopre che non cercano sei "
    "cose diverse: ne cercano tre. “Il Metodo Vincente” cerca due ambi che "
    "hanno la stessa somma <i>dentro ciascuna ruota</i>. “Fulmine” e "
    "“Un Solo Ambo Secco” cercano invece numeri che si accoppiano "
    "<i>incrociando le due ruote</i>, sempre con la stessa somma — e questo, "
    "negli esempi del Fulmine, non salta all’occhio, perché le coppie a "
    "somma uguale non sono gli ambi usciti ma il loro incrocio. “Lotto Facile "
    "4” cerca numeri a distanza 30, cioè le terzine simmetriche. Tutto il "
    "resto sono filtri e formule che si applicano dopo."))

# ---------------------------------------------------------------- 4
A(P("Dove abbiamo dovuto decidere noi", "h1"))
A(P("Su alcuni punti i fascicoli sono ambigui, incompleti o contengono refusi. "
    "In quei casi abbiamo scelto un’interpretazione, sempre quella che "
    "riproduce gli esempi pubblicati dagli autori — ma sono scelte, non "
    "verità. Se su qualcuna di queste la pensi diversamente, si cambia: basta "
    "dirlo, e il sito si ricalcola da capo."))

A(P("Il refuso di Lotto Facile 5", "h2"))
A(P("Alla riga 39 della tabella, la colonna degli ambi secchi stampa 18-57, mentre "
    "l’esempio statistico dello stesso fascicolo (19 gennaio 2000) gioca 18-27. "
    "Tutte le altre righe seguono la regola “ambata più primo elemento "
    "della terzina”, che darebbe appunto 18-27. Abbiamo implementato la tabella "
    "<b>alla lettera, refuso compreso</b>, segnalandolo nel codice: così si "
    "possono misurare tutt’e due le versioni senza doversene ricordare."))

A(P("Il refuso di Lotto Facile 4", "h2"))
A(P("Nella tabella statistica, il caso del 2 giugno 1999 riporta “NA 55-22”. "
    "Con quei numeri la condizione non è soddisfatta e non esce l’ambata "
    "pubblicata. Con “NA 52-22” torna tutto. Abbiamo verificato tutti e 37 "
    "i casi della tabella e gli altri 36 tornano esattamente."))

A(P("Le “ruote contigue” del Fulmine", "h2"))
A(P("Manara scrive che le due ruote devono essere contigue, ma non dice che cosa "
    "voglia dire, e i suoi stessi esempi usano Milano-Palermo e Roma-Venezia, che "
    "non sono né consecutive né diametrali. Per ora il vincolo è "
    "<b>spento</b>: si prendono tutte le coppie di ruote. Se tu sai che cosa "
    "intendeva, lo accendiamo."))

A(P("Le “verifiche di armonia” che non verificano nulla", "h2"))
A(P("Tre metodi chiedono di controllare certe uguaglianze fra i numeri prima di "
    "giocare. Facendo i conti, quelle uguaglianze sono <b>sempre vere</b> quando "
    "è vera la condizione d’ingresso: non scartano niente. Nel Fulmine, "
    "per esempio, il “controllo diviso due” restituisce per forza il numero "
    "più grande, qualunque siano i quattro numeri. Le abbiamo tenute come "
    "controlli interni — se un giorno non tornassero, vorrebbe dire che "
    "c’è un errore nel programma — ma non come filtri."));

A(P("L’Ambo Secco Caotico: la formula ricostruita", "h2"))
A(P("Questo era il più difficile, perché il foglio di Antonio Longo è "
    "materiale pubblicitario: il metodo vero si comprava. L’unico esempio "
    "è “NA 41 — MI 49 — VE 41 = 41 x 90 + 49 = 37.39 = 85.49”. "
    "La chiave era che la stessa espressione va letta in due modi: 41×90 fa "
    "3690, più 49 fa 3739, che spezzato a metà dà <b>37 e 39</b>; e "
    "le due metà di 3690, cioè 36 e 90, ciascuna sommata a 49, danno "
    "<b>85 e 49</b>. Entrambi gli ambi pubblicati vengono fuori esatti, senza "
    "inventare nessuna costante."))
A(P("Quello che resta incerto non è la formula ma la <b>condizione di ricerca</b>: "
    "quando applicarla. Dall’unico esempio sembra che serva un numero che esce "
    "su due ruote diverse (il 41 su Napoli e Venezia) più il suo complemento a "
    "90 su una terza (il 49 su Milano). È un’ipotesi costruita su un caso "
    "solo. Se ti capitasse sotto mano un secondo esempio di questo metodo, sarebbe "
    "la cosa più utile che potresti darci."))

# ---------------------------------------------------------------- 5
A(P("Che cosa il sito può fare, e che cosa no", "h1"))

A(P("Quello che fa bene", "h2"))
A(punti([
    "Applica i sei metodi a <b>ogni</b> estrazione e a <b>tutte</b> le combinazioni "
    "di ruote, senza saltarne una e senza sbagliare un conto.",
    "Tiene il conto dei colpi: sa quali previsioni sono ancora vive e quante "
    "estrazioni restano a ciascuna.",
    "Verifica da solo gli esiti e li registra, senza dimenticarsene.",
    "Dice quanto costa una giocata e con quale probabilità si vince, prima di "
    "giocarla.",
]))

A(P("Quello che non può fare", "h2"))
A(P("Prevedere l’estrazione. E qui serve dire una cosa che nei fascicoli non "
    "si legge mai."))
A(P("Abbiamo provato tutti e sei i metodi su <b>vent’anni di estrazioni vere</b>, "
    "quasi 24.000 rilevamenti, confrontandoli con giocate scelte a caso della stessa "
    "ampiezza. Il risultato è che nessuno dei sei si distingue dal caso, e che "
    "ogni euro giocato ne restituisce in media fra 62 e 74 centesimi, a seconda del "
    "metodo. Non è un difetto di questo o quel metodo: è il margine del "
    "banco, ed è lo stesso qualunque numero si giochi. I metodi scelgono "
    "<i>quali</i> numeri giocare, non <i>quanto paga</i> il gioco."))

A(riquadro([
    "<b>Le percentuali dei fascicoli non sono probabilità.</b> Quando un "
    "fascicolo annuncia il 97% o addirittura il 601%, sta contando le vincite "
    "diviso le previsioni — e una previsione che dà più vincite le "
    "conta tutte. Con 14 colpi, 2 ruote, un’ambata, tre ambi e una terzina "
    "giocata anche a Tutte, è difficile <i>non</i> prendere qualcosa. La "
    "domanda vera non è “quante volte esce” ma “quanto ho speso "
    "per farlo uscire”, ed è esattamente quello che mostra la pagina "
    "Bilancio.",
]))

A(P("Perché allora vale la pena averlo", "h2"))
A(P("Perché è uno strumento di calcolo e di disciplina, non un indovino. "
    "Fa i conti al posto tuo e li fa giusti; ti dice quanto stai spendendo mentre "
    "lo stai spendendo; e se un giorno uno dei metodi dovesse davvero funzionare "
    "meglio degli altri, questa è l’unica maniera per accorgersene sul "
    "serio invece che a impressione."))

A(P("Il gioco può causare dipendenza patologica. Le cifre della pagina "
    "Bilancio sono lì apposta: servono a decidere con gli occhi aperti quanto "
    "si vuole spendere.", "piede"))

A(P("Se qualcosa non torna", "h1"))
A(punti([
    "<b>La pagina sembra ferma a giorni fa.</b> Guarda la riga in cima: dice "
    "sempre di quando sono i dati. Se c’è l’avviso rosso, "
    "l’aggiornamento automatico ha avuto un problema — dillo a Pierre, si "
    "risolve in due minuti.",
    "<b>Non compare nessuna previsione.</b> Può succedere: vuol dire che "
    "nelle ultime estrazioni nessuno dei sei metodi ha trovato la sua "
    "configurazione, o che tutte le previsioni hanno esaurito i colpi.",
    "<b>Un numero ti sembra sbagliato.</b> Segnalalo. Ogni previsione è "
    "registrata con il giorno, le ruote e i numeri: si può sempre rifare il "
    "conto a mano e vedere chi ha ragione.",
]))

A(Spacer(1, 2))
A(riquadro([
    "Senza i tuoi fascicoli non ci sarebbe niente di tutto questo: i sei metodi "
    "vengono da lì, e le scelte più delicate — quale interpretazione "
    "dare a un passaggio ambiguo, quale refuso correggere — sono ancora tue "
    "da fare.",
]))

doc = SimpleDocTemplate(
    str(Path(__file__).with_name("App_Lotto_guida.pdf")), pagesize=A4,
    leftMargin=2.3 * cm, rightMargin=2.3 * cm,
    topMargin=2.1 * cm, bottomMargin=2.1 * cm,
    title="App Lotto — guida", author="Pierre")
doc.build(storia, onFirstPage=intestazione_pagina, onLaterPages=intestazione_pagina)
print("fatto")
