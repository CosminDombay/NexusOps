# 4.6 Proiectarea frontend-ului

## 1. Prezentare generală

Frontend-ul NexusOps reprezintă interfața principală prin care utilizatorii interacționează cu platforma de orchestrare a infrastructurii. Scopul său este să transforme funcțiile backend-ului, precum inventarierea nodurilor, provisioning-ul, execuția de joburi, deployment-urile Docker Compose, managementul credentialelor, orchestrarea identității Linux și monitorizarea runtime, într-un spațiu operațional coerent și accesibil.

În arhitectura NexusOps, frontend-ul nu are rolul de a executa direct operații asupra infrastructurii. El nu se conectează direct la Proxmox, nu deschide conexiuni SSH independente și nu gestionează secretele în mod autonom. Rolul său este să prezinte starea sistemului, să permită utilizatorului să formuleze intenții operaționale și să transmită aceste intenții către backend. Backend-ul rămâne componenta care validează, autorizează, orchestrează și persistă operațiile.

Alegerea unei interfețe web este justificată de natura centralizată a platformei. NexusOps trebuie să poată fi accesat de administratori, operatori și utilizatori cu rol de vizualizare dintr-un punct comun, fără instalarea unor instrumente locale specializate pe fiecare stație. O aplicație web permite acces controlat prin browser, actualizare centralizată a interfeței, integrare naturală cu autentificarea platformei și posibilitatea de a afișa date operaționale complexe într-un mod structurat.

Administrarea centralizată oferă mai multe beneficii. Operatorii pot vedea inventarul, starea infrastructurii, istoricul joburilor, deployment-urile, workflow-urile și monitoring-ul din aceeași interfață. Administratorii pot controla accesul, credentialele și integrările fără a distribui secrete sau configurații locale. În același timp, utilizatorii cu drepturi de vizualizare pot consulta starea platformei fără a putea declanșa operații riscante. Astfel, frontend-ul contribuie la obiectivul general al NexusOps: reducerea fragmentării operaționale și creșterea trasabilității.

Din punct de vedere tehnologic, frontend-ul este o aplicație React, TypeScript, Vite și TailwindCSS. React oferă modelul componentizat necesar unei aplicații operaționale complexe, TypeScript reduce riscul de inconsistență între datele primite de la backend și interfață, Vite susține un flux eficient de dezvoltare, iar TailwindCSS permite construirea rapidă a unei interfețe dense, orientate spre lucru.

[Figura 4.12 – Arhitectura generală a frontend-ului]

---

## 2. Organizarea interfeței utilizator

Interfața utilizator este organizată în jurul unui shell persistent de aplicație. După autentificare, utilizatorul vede o zonă de navigare laterală și o zonă principală de conținut. Navigarea este grupată logic în zone precum Core și Operations/Orchestration. Această structură separă zonele fundamentale, cum ar fi Inventory, Infrastructure, Provisioning și Credentials, de zonele operaționale, cum ar fi Jobs, Workflows, Automations, Packages, Profiles, Deployments, Identity, Monitoring, Integrations, Trash și Users & RBAC.

Structura de navigare este influențată de rolul utilizatorului. Un utilizator cu rol viewer are acces la zone de vizualizare, precum Inventory, Infrastructure, Monitoring și Workflows. Un operator poate accesa zone de execuție operațională, precum Provisioning, Deployments, Packages, Profiles, Jobs, Automations și Host Tools. Un administrator are acces la zone sensibile, precum Credentials, Identity, Integrations, Trash și Users & RBAC. Această filtrare a navigării nu înlocuiește securitatea backend-ului, dar oferă o experiență coerentă și reduce expunerea vizuală a funcțiilor nepermise.

Principalele arii funcționale ale interfeței sunt construite în jurul fluxurilor reale de lucru ale platformei. Inventory este punctul de pornire pentru administrarea nodurilor. Infrastructure oferă vizibilitate asupra Proxmox și asupra relației dintre resursele descoperite și inventarul administrat. Jobs permite execuții operaționale și consultarea istoricului. Provisioning creează noduri noi. Deployments controlează aplicații Docker Compose. Identity gestionează utilizatori și permisiuni Linux. Monitoring oferă readiness operațional, iar Workflows și Automations explică și declanșează procese compuse.

Experiența utilizatorului este proiectată pentru administrare operațională, nu pentru prezentare comercială. Paginile folosesc liste, tabele, carduri de stare, badge-uri runtime, panouri de detalii, acțiuni contextuale și modalități de filtrare. Interfața trebuie să permită scanarea rapidă a stării sistemului, identificarea problemelor și declanșarea operațiilor necesare cu confirmări adecvate pentru acțiunile distructive.

Un principiu important al organizării interfeței este separarea dintre contextul principal și acțiunile secundare. NexusOps folosește din ce în ce mai mult un model de tip „listă sau explorer -> context operațional -> drawer sau modal pentru creare/editare/configurare”. Astfel, formularele lungi nu ocupă permanent pagina principală, iar utilizatorul păstrează vizibil contextul operațional în timp ce configurează o entitate. Componente precum ContextDrawer, TargetSelector, ExecutionVariablesModal, runtime badges și operational timelines contribuie la această experiență unitară.

[Figura 4.13 – Organizarea interfeței utilizator]

---

## 3. Modulele principale ale interfeței

Dashboard-ul și zona Inventory reprezintă punctul central al interfeței. Ele oferă o imagine asupra nodurilor administrate, stării acestora, metadatelor de provider, readiness-ului SSH, stării runtime și relației cu Proxmox sau alte surse. Utilizatorul poate crea sau importa hosturi, poate consulta detalii, poate edita metadate, poate arhiva sau elimina înregistrări și poate accesa operații legate de host. Informațiile afișate includ hostname, IP, tip de nod, stare de management, stare de sincronizare, stări runtime și avertismente operaționale.

Modulul Inventory este proiectat ca un spațiu CMDB operațional. El nu este doar o listă simplă de servere, ci reprezintă punctul prin care celelalte module aleg ținte administrabile. De aceea, interfața pune accent pe stări, badge-uri, readiness și acțiuni contextuale. Utilizatorul este ghidat să lucreze cu noduri cunoscute de platformă, nu cu adrese IP introduse arbitrar.

Provisioning oferă un flux pentru crearea de VM-uri sau containere LXC prin Proxmox. Interfața include selecția template-ului, configurarea resurselor, setările cloud-init, rețeaua statică, discurile, blueprint-urile și planul de bootstrap. Utilizatorul poate porni de la un blueprint pentru valori repetabile, dar păstrează controlul asupra valorilor specifice fiecărei mașini, cum ar fi numele, VMID-ul, hostname-ul și adresa IP. Informațiile afișate includ istoricul cererilor de provisioning, starea lifecycle și rezultatul operațiilor.

Deployments este proiectat ca un dashboard operațional pentru servicii Docker Compose. Utilizatorul vede deployment-uri sub formă de carduri de serviciu, cu stări runtime, health, sync, hosturi țintă, execuții recente, output, durată, porturi, sursa Compose și indicatori pentru credentiale. Interacțiunile principale includ creare, editare, preview, deploy, redeploy, restart, stop, logs, inspect și refresh runtime. Interfața separă secretele de mediu de credentialul de execuție/sudo, reflectând decizia arhitecturală a backend-ului.

Identity Management oferă o interfață pentru administrarea identității Linux pe hosturile administrate. Utilizatorul poate crea sau adopta utilizatori, grupuri, chei SSH și template-uri de permisiuni, apoi le poate replica pe hosturi selectate. Interfața este ghidată, incluzând access profiles, group presets, permission presets și controale avansate pentru utilizatori cu experiență. Informațiile afișate includ starea utilizatorilor, grupurile, permisiunile, hosturile observate și rezultatele replicării.

Monitoring & Runtime oferă o imagine asupra readiness-ului operațional. Modulul nu încearcă să înlocuiască Grafana, Prometheus sau Loki. În schimb, afișează stări persistente despre disponibilitatea componentelor de monitorizare, exportere, staleness, health provider și readiness pe noduri. Utilizatorul poate consulta rapid ce noduri sunt monitorizate, parțial monitorizate, stale sau lipsite de componente necesare.

Credential Manager permite administrarea secretelor reutilizabile. Utilizatorul poate crea, edita metadate, consulta tipuri și scope-uri, șterge sau restaura credentiale. Interfața nu afișează valorile secrete după creare, ci doar informații mascate și metadate. Acest modul susține fluxurile din Inventory, Jobs, Deployments, Identity, Integrations, Packages și Profiles.

Remote Access oferă un workspace pentru acces la hosturi administrate. Interfața include browser de fișiere, editor pentru fișiere remote și terminal persistent. Conexiunea shell folosește un token scurt obținut de la backend înainte de deschiderea WebSocket-ului. Interacțiunile sunt limitate de rol și de starea hostului, iar frontend-ul nu expune credentiale SSH.

Automation & Workflows oferă vizibilitate asupra proceselor operaționale. Automations permite definirea unor execuții programate sau declanșate manual, iar Workflows afișează pași, durate, stări, rezultate și legături către joburi. Aceste module ajută utilizatorul să înțeleagă nu doar ce comandă s-a executat, ci și de ce a fost executată și în ce proces mai larg s-a încadrat.

[Tabelul 4.7 – Modulele principale ale frontend-ului]

| Modul | Scop | Interacțiuni utilizator | Informații afișate |
| --- | --- | --- | --- |
| Dashboard / Inventory | Administrarea nodurilor și vizualizarea stării infrastructurii | creare, import, editare, arhivare, acces detalii | noduri, stări lifecycle, runtime, readiness, metadate provider |
| Provisioning | Crearea VM/LXC prin Proxmox | selectare template, configurare resurse, blueprint, bootstrap | status provisioning, configurație, istoric, rezultat |
| Deployments | Administrarea aplicațiilor Docker Compose | create/edit, preview, deploy, restart, logs, inspect | stare deployment, ținte, runtime, health, execuții |
| Identity Management | Orchestrarea utilizatorilor și permisiunilor Linux | creare/adoptare, replicare, preseturi, target selection | utilizatori, grupuri, chei SSH, permisiuni, rezultate |
| Monitoring & Runtime | Observabilitate operațională și readiness | refresh, consultare stări, deschidere linkuri Grafana | provider health, exporters, stale state, readiness |
| Credential Manager | Administrarea secretelor reutilizabile | creare, editare, ștergere, restaurare | tip credential, scope, stare mascată, referințe |
| Remote Access | Acces interactiv la hosturi administrate | shell, navigare fișiere, citire/scriere controlată | fișiere, terminal, stare conexiune |
| Automation & Workflows | Execuții programate și vizibilitate multi-pas | creare automatizări, run now, consultare timeline | stări, pași, durate, rezultate, joburi asociate |

---

## 4. Comunicarea cu backend-ul

Comunicarea frontend-backend este bazată în principal pe REST. Frontend-ul folosește un client HTTP comun pentru a trimite cereri JSON către API-ul backend-ului. Fiecare feature definește propriile funcții de acces la date și tipuri TypeScript, dar transportul este centralizat. Această abordare asigură consistență în tratarea tokenurilor, a erorilor și a bazei URL configurabile.

Fluxul de autentificare începe cu pagina de login, unde utilizatorul introduce username sau email și parolă. Backend-ul returnează un access token, un refresh token și datele utilizatorului. Frontend-ul păstrează sesiunea în storage de sesiune și atașează access token-ul la cererile ulterioare prin headerul Authorization. La expirarea access token-ului, clientul încearcă automat refresh-ul sesiunii. Dacă refresh-ul eșuează, datele locale sunt curățate și utilizatorul este redirecționat către login.

Schimbul de date este orientat pe contracte clare între frontend și backend. Interfața primește entități precum servere, joburi, deployment-uri, workflow-uri, credentiale mascate, snapshoturi monitoring și stări runtime. Pentru operații sensibile, frontend-ul trimite referințe către credentiale, nu valori secrete. De exemplu, în package/profile/deployment execution, valorile sensibile sunt selectate ca referințe către Credential Manager, iar rezolvarea efectivă are loc în backend.

WebSocket-ul este folosit într-un caz specific: shell-ul interactiv din Remote Access. Înainte de conectare, frontend-ul cere backend-ului un token scurt, scoped, pentru hostul respectiv. Abia apoi construiește URL-ul WebSocket și deschide conexiunea. Această decizie separă accesul interactiv de fluxul REST obișnuit și evită transmiterea tokenului JWT principal ca parametru de WebSocket.

Operațiile „real-time” din NexusOps sunt tratate pragmatic. Majoritatea paginilor folosesc polling, refresh manual sau reîncărcarea controlată a datelor, nu streaming permanent. Jobs, Deployments, Workflows, Automations, Monitoring și Runtime citesc stări persistate de backend. Această abordare este potrivită pentru stadiul actual al platformei deoarece reduce complexitatea, păstrează sistemul auditabil și evită dependența de un bus de evenimente sau de infrastructură de streaming.

Fluxul conceptual al comunicării poate fi descris astfel: utilizatorul interacționează cu o pagină; pagina apelează un modul API din feature; modulul folosește clientul HTTP comun; backend-ul validează tokenul și rolul; răspunsul este transformat în stare UI; utilizatorul vede rezultatul sub formă de carduri, tabele, badge-uri, timeline-uri sau panouri de detalii. Pentru shell interactiv, REST este folosit pentru obținerea tokenului scoped, iar WebSocket-ul este folosit doar pentru fluxul interactiv de terminal.

[Figura 4.14 – Fluxul de comunicare frontend-backend]

---

## 5. Principii de proiectare

Consistența este un principiu central al frontend-ului. Paginile operaționale folosesc aceleași modele vizuale pentru stări, acțiuni, filtre, target selection, confirmări și rezultate. Runtime badges, status pills, PageHeader, ContextDrawer, TargetSelector și operational timelines reduc diferențele dintre module și ajută utilizatorul să înțeleagă mai rapid interfața.

Usability în NexusOps înseamnă eficiență pentru administratori și operatori, nu simplificare excesivă. Interfața trebuie să prezinte multe date tehnice, dar într-o formă scanabilă și organizată. De aceea, paginile folosesc carduri operaționale, tabele responsive, panouri de detalii, drawer-e contextuale și moduri avansate pentru controale Linux mai complexe.

Responsiveness este necesară deoarece interfața trebuie să rămână utilizabilă pe dimensiuni diferite de ecran. Listele se pot adapta între tabele și carduri, navigarea laterală devine scrollabilă, iar formularele lungi sunt plasate în drawer-e sau panouri scrollabile. Această abordare permite utilizarea platformei atât pe ecrane mari de administrare, cât și pe ecrane mai mici pentru verificări rapide.

Reusability apare prin componente și pattern-uri comune. TargetSelector este folosit pentru alegerea hosturilor în operații multiple. ExecutionVariablesModal standardizează introducerea variabilelor și selecția credentialelor. ContextDrawer standardizează fluxurile de creare și editare. Componentele operaționale pentru badge-uri, timeline-uri și acțiuni oferă o experiență comună între Jobs, Deployments, Workflows și alte module.

Operational efficiency se reflectă în faptul că interfața este construită pentru fluxuri reale de administrare. Utilizatorul poate porni de la Inventory, poate vedea readiness, poate aplica un profil, poate rula un job, poate verifica outputul și poate consulta runtime state fără a schimba instrumentul. Acțiunile destructive sunt separate și confirmate, iar rezultatele sunt afișate în apropierea contextului operațional relevant.

[Tabelul 4.8 – Principiile de proiectare ale frontend-ului]

| Principiu | Aplicare în NexusOps | Beneficiu |
| --- | --- | --- |
| Consistency | Componente comune pentru stări, acțiuni, drawer-e și selecție de ținte | Învățare mai rapidă și experiență uniformă |
| Usability | Layout-uri dense, scanabile, orientate spre operații | Eficiență pentru administratori și operatori |
| Responsiveness | Tabele/carduri adaptive, sidebar scrollabil, panouri flexibile | Utilizare pe ecrane diferite |
| Reusability | TargetSelector, ContextDrawer, ExecutionVariablesModal, runtime badges | Reducerea duplicării și coerență vizuală |
| Operational efficiency | Fluxuri centrate pe inventar, joburi, runtime și acțiuni contextuale | Execuție rapidă și controlată a operațiilor |

---

## 6. Concluzii

Frontend-ul NexusOps a fost proiectat ca o interfață operațională centralizată pentru administrarea infrastructurii Linux. Obiectivul său principal este să ofere utilizatorilor o imagine coerentă asupra inventarului, stării runtime, operațiilor administrative și proceselor de orchestrare, fără a expune direct infrastructura sau credentialele către browser.

Din perspectiva experienței utilizatorului, interfața urmărește să fie densă, clară și orientată spre acțiune. Ea nu este o pagină de prezentare, ci un spațiu de lucru pentru administratori și operatori. Navigarea pe roluri, componentele comune, drawer-ele contextuale, target selection-ul, badge-urile runtime și timeline-urile operaționale contribuie la o experiență care susține decizii rapide și acțiuni controlate.

Frontend-ul susține platforma NexusOps prin faptul că face accesibile funcțiile backend-ului într-un mod unitar. Inventory, Provisioning, Deployments, Identity, Monitoring, Credentials, Remote Access, Automations și Workflows nu sunt prezentate ca instrumente izolate, ci ca părți ale aceleiași platforme de orchestrare. Prin această organizare, frontend-ul contribuie direct la obiectivele NexusOps: administrare centralizată, reducerea erorilor operaționale, vizibilitate asupra stării infrastructurii și control securizat asupra acțiunilor administrative.
