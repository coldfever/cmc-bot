# Botul Critical Miss Club

Un singur bot pentru tot serverul CMC: structura serverului, bun venit, alegerea jocurilor, turnee, schimburi/vânzări, căutare de cărți, știri și log de moderare. Tot codul și toată configurația stau în acest folder. Dacă e pe GitHub, nu se mai pierde nimic.

> **Regula de aur:** tokenul botului nu se scrie niciodată în cod, în chat sau pe GitHub. Stă doar în Railway, la „Variables”. Dacă a scăpat undeva, apasă **Reset Token** în Developer Portal și pune noul token în Railway.

---

## Ce face

| Comandă | Cine | Ce face |
|---|---|---|
| `/configureaza-server` | admin | Creează rolurile, categoriile și canalele lipsă din `config/server.yaml`. Implicit e **simulare** și nu șterge niciodată nimic. |
| `/panou-roluri` | admin | Postează în `#alege-jocurile` iconițele (butoanele) din care membrii își aleg jocurile și ping-urile de turneu. |
| `/membri-existenti` | admin | Dă rolul **Membru** tuturor celor care erau deja pe server (o singură dată, când pornești verificarea). |
| `/posteaza-regulament` | admin | Postează regulamentul (text în `bot/cogs/admin.py`) cu butonul **„Accept regulamentul”**. |
| `/verifica-bot` | admin | Verifică permisiunile, poziția rolului, canalele și setările. |
| `/anunta` | staff | Anunț oficial frumos formatat, opțional cu @everyone. |
| `/eveniment creeaza` | staff | Anunță un turneu în canalul jocului, cu ping la rol, butoane Vin / Poate / Nu vin, limită de locuri cu listă de așteptare, plus adăugare în calendarul Discord. Trimite remindere automate cu 24h și 1h înainte. |
| `/eveniment anuleaza` · `participanti` · `lista` | staff / toți | Gestionarea evenimentelor. |
| `/rezultate` | staff | Publică clasamentul în `#rezultate-turnee`. |
| `/anunt-schimb` | toți | Anunț de Vând / Cumpăr / Schimb / Licitație în canalul de schimburi al jocului, cu formular fix. Anunțul expiră automat după 30 de zile. |
| `/finalizat` | autorul | Închide anunțul (comanda se dă în firul anunțului). |
| `/rep` · `/reputatie` | toți | Reputație după tranzacții reușite (o dată pe săptămână per persoană). |
| `/card` | toți | Caută o carte Magic sau Pokemon, cu imagine și preț. |
| `/stiri adauga` · `lista` · `sterge` | admin | Postează automat știri din fluxuri RSS (site-uri, canale YouTube) în canalul ales. Înlocuiește vechiul bot de news. |
| *(automat)* | – | Mesaj de bun venit în `#bun-venit` și log de mesaje șterse/editate, intrări și ieșiri în `#mod-log`. |

**Muzică:** nu am inclus. Boții de muzică se strică des din cauza restricțiilor YouTube și consumă mult. Recomand un bot public de muzică, adăugat direct din site-ul lui, fără găzduire.

---

## Pasul 1 – Curățenie boți vechi (5 minute)

1. În Discord: **Setări server → Integrări**. Acolo vezi toți boții de pe server. Notează-i, apoi dă **Kick** celor vechi pe care nu-i mai folosești (de exemplu cel de news).
2. Mergi pe <https://discord.com/developers/applications>. Acolo sunt aplicațiile (boții) create de tine. Dacă le recunoști pe cele vechi, le poți șterge: **General Information → Delete App**. Dacă nu ești sigur, lasă-le; fără tokenul lor nu fac nimic.

## Pasul 2 – Creează botul nou

1. Pe <https://discord.com/developers/applications> → **New Application** → nume: `CMC Bot`.
2. Tab-ul **Bot**:
   - **Reset Token** → copiază tokenul și păstrează-l doar pentru Railway (Pasul 4).
   - Activează **Server Members Intent** și **Message Content Intent** → **Save**.
3. Tab-ul **OAuth2 → URL Generator**:
   - Scopes: bifează `bot` și `applications.commands`.
   - Bot Permissions: bifează `Administrator`. E nevoie de el ca să creeze canale și roluri; poți reduce mai târziu.
   - Deschide linkul generat → alege serverul Critical Miss Club → **Autorizează**.
4. În Discord: **Setări server → Roluri** → trage rolul `CMC Bot` **deasupra** rolurilor de joc, ca să le poată da membrilor.
5. Recomandat: **Setări server → Activează Community**. Fără asta nu există canale Forum, iar botul face canale text obișnuite în locul lor.

## Pasul 3 – Pune codul pe GitHub

1. Creează un repository **privat** pe <https://github.com/new>, de exemplu `cmc-bot`.
2. Încarcă tot conținutul acestui folder (**Add file → Upload files**). Fișierul `.env` nu trebuie încărcat niciodată.

## Pasul 4 – Pornește botul pe Railway

1. Intră pe <https://railway.com> cu contul de GitHub.
2. **New Project → Deploy from GitHub repo** → alege `cmc-bot`. Railway vede singur `Dockerfile`-ul.
3. În serviciu, tab-ul **Variables**, adaugă:
   - `DISCORD_TOKEN` = tokenul din Pasul 2
   - `GUILD_ID` = `1461340905385492545`
   - `DATA_DIR` = `/data`
4. Click dreapta pe serviciu (sau **Settings**) → **Add Volume** → mount path: `/data`. Aici se păstrează evenimentele, reputația și știrile între restarturi; fără volum se pierd la fiecare update.
5. **Deploy**. În **Logs** trebuie să apară `Conectat ca CMC Bot`.

Planul Hobby de pe Railway costă ~5 $/lună și ajunge din plin pentru botul ăsta.

## Pasul 5 – Prima configurare pe server

În orice canal, ca admin:

1. `/verifica-bot` → rezolvă ce apare cu ❌.
2. `/configureaza-server` (simulare) → citește lista cu ce ar crea.
3. `/configureaza-server simulare:False` → creează efectiv.
4. Mută manual ce era în categoria veche **Text Channels**, apoi șterge-o.
5. `/posteaza-regulament`, apoi `/panou-roluri`.
6. **Schimburi-vanzari → Forum.** Canalul `#schimburi-vanzari` existent la Pokemon e canal text, iar Discord nu permite transformarea în forum. Ai două variante:
   - îl lași așa, iar `/anunt-schimb` merge și în canal text (fiecare anunț primește fir propriu);
   - sau îl redenumești în `schimburi-vanzari-vechi`, rulezi din nou `/configureaza-server simulare:False` (creează forumul cu etichete) și arhivezi canalul vechi.
7. Opțional: `/stiri adauga` pentru fluxurile de știri dorite (link RSS, de exemplu un canal YouTube: `https://www.youtube.com/feeds/videos.xml?channel_id=...`).

**Despre `ascunde_jocuri_fara_rol`:** în config e `false`, deci toată lumea vede toate jocurile. După ce membrii își aleg rolurile din `#alege-jocurile` (anunță-i), îl poți pune pe `true` și rulezi `/configureaza-server simulare:False actualizeaza_permisiuni:True`. Atunci fiecare vede doar jocurile lui.

---

## Cum intră un membru nou

1. Vede doar categoria **Bun venit**: `#bun-venit`, `#regulament`, `#anunturi`.
2. Citește `#regulament` și apasă **✅ Am citit și accept regulamentul** → primește rolul **Membru** și vede restul serverului (Magazin, Comunitate, Voce) plus `#alege-jocurile`.
3. În `#alege-jocurile` apasă pe iconița fiecărui joc pe care îl joacă → îi apar doar categoriile acelor jocuri. Al doilea set de butoane (🏆) e pentru ping la turnee.

Se controlează din `config/server.yaml`: `verificare.activ` și `ascunde_jocuri_fara_rol`.

**Pornirea verificării pe un server care are deja membri** (ordinea contează, altfel membrii existenți pierd accesul):
1. `/configureaza-server simulare:False` – creează rolul Membru.
2. `/membri-existenti` – le dă rolul tuturor celor de pe server.
3. `/configureaza-server simulare:False actualizeaza_permisiuni:True` – ascunde serverul pentru cei fără rol.
4. Șterge mesajele vechi din `#regulament` și `#alege-jocurile`, apoi `/posteaza-regulament` și `/panou-roluri`.
5. Anunță în `#anunturi` că fiecare trebuie să-și aleagă jocurile din `#alege-jocurile`.

---

## Cum schimbi ceva mai târziu

- **Canal, categorie, rol sau joc nou:** editezi `config/server.yaml` (direct pe GitHub, cu creionul), dai **Commit**, Railway repornește singur botul, apoi rulezi `/configureaza-server`.
- **Textul regulamentului:** `bot/cogs/admin.py`.
- **Un joc nou** (de exemplu Lorcana): copiezi un bloc din `jocuri:` în config și schimbi numele, rolul și categoria.

## Structura fișierelor

```
config/server.yaml     ← structura serverului (singurul fișier de editat de obicei)
bot/main.py            ← pornirea botului
bot/cogs/              ← câte un fișier pentru fiecare funcție
Dockerfile, railway.json, requirements.txt  ← pentru Railway
.env.example           ← model de variabile (pentru rulare locală)
```

## Rulare pe calculator (opțional, pentru teste)

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env    # și pune tokenul în .env
python -m bot.main
```
Nu rula botul în același timp și local, și pe Railway.
