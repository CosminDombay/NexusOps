# 4.5 Proiectarea backend-ului

## 1. Prezentare generală

Backend-ul reprezintă componenta centrală de coordonare a platformei NexusOps. În cadrul sistemului, frontend-ul oferă interfața de interacțiune pentru operatori și administratori, baza de date păstrează starea persistentă, iar sistemele externe precum Proxmox, Docker, Prometheus, Loki sau hosturile Linux furnizează infrastructura administrată. Backend-ul este elementul care leagă aceste componente într-un flux controlat, securizat și auditabil.

Rolul backend-ului nu este limitat la expunerea unei interfețe HTTP pentru frontend. El funcționează ca un plan de control operațional, responsabil pentru validarea cererilor, aplicarea regulilor de securitate, interpretarea intenției utilizatorului, coordonarea operațiunilor asupra infrastructurii și persistarea rezultatelor. Toate acțiunile importante trec prin backend, deoarece acesta deține contextul complet: utilizatorul autentificat, rolul acestuia, nodul de infrastructură vizat, credentialele disponibile, starea inventarului și istoricul operațional.

Backend-ul este componenta centrală de orchestrare deoarece NexusOps nu permite frontend-ului să comunice direct cu infrastructura administrată. Interfața web nu execută comenzi SSH, nu apelează direct Proxmox și nu accesează direct credentiale. În schimb, frontend-ul trimite intenții operaționale către backend, iar backend-ul decide dacă operația este permisă, ce resurse sunt implicate, ce credentiale trebuie rezolvate, ce pași trebuie executați și cum se persistă rezultatul. Această abordare reduce riscul operațional și oferă un model coerent de audit.

Responsabilitățile principale ale backend-ului sunt autentificarea și autorizarea utilizatorilor, administrarea inventarului, orchestrarea operațiunilor prin Jobs și Workflows, integrarea cu Proxmox și alte sisteme externe, protejarea credentialelor, coordonarea deployment-urilor Docker Compose, orchestrarea identității Linux, menținerea stării runtime și furnizarea unei imagini consistente către frontend.

Interacțiunea cu baza de date se realizează printr-un model persistent, în care entitățile centrale precum Inventory, Jobs, Credentials, Users, Deployments, Workflows și Monitoring Snapshots sunt stocate relațional. Interacțiunea cu infrastructura este realizată prin adaptoare și servicii specializate, astfel încât logica de business să nu depindă direct de detaliile tehnice ale unui provider. Din perspectivă sistemică, backend-ul este mediatorul dintre intenția operatorului și execuția efectivă asupra infrastructurii.

[Figura 4.7 – Arhitectura generală a backend-ului]

---

## 2. Arhitectura logică a backend-ului

Backend-ul NexusOps este proiectat ca un modular monolith bazat pe FastAPI. Această alegere permite organizarea aplicației în domenii funcționale clare, fără complexitatea operațională a unei arhitecturi distribuite cu microservicii. Fiecare domeniu are responsabilități proprii, însă toate rulează în aceeași aplicație backend, folosind același model de autentificare, aceeași bază de date și aceleași mecanisme de execuție operațională.

Stratul API reprezintă punctul de intrare pentru cererile venite din frontend. Scopul său este să primească cereri HTTP sau WebSocket, să valideze forma datelor, să aplice dependențele de autentificare și autorizare și să transforme răspunsurile domeniului în răspunsuri potrivite pentru interfața web. Acest strat nu trebuie să conțină logica principală de business. El acționează ca un strat de expunere, păstrând separarea între contractele externe și mecanismele interne ale platformei.

Stratul de logică de business conține regulile operaționale ale platformei. Aici sunt coordonate fluxuri precum importul din Proxmox, provisioning-ul, aplicarea unui profil, executarea unui package, replicarea identității Linux sau lansarea unui deployment Docker Compose. Acest strat interpretează intenția utilizatorului și decide ce entități sunt implicate, ce validări sunt necesare și ce operațiuni trebuie executate. El este responsabil pentru coerența proceselor și pentru respectarea limitelor arhitecturale, precum regula conform căreia operațiile trebuie să vizeze noduri din Inventory.

Stratul de persistență izolează accesul la baza de date. Responsabilitatea sa este stocarea, citirea și actualizarea entităților persistente. În NexusOps, acest strat permite ca domeniile să folosească modele relaționale și tranzacții fără ca stratul API să manipuleze direct datele. Prin această separare, logica de business poate fi exprimată în termeni de operații de domeniu, iar detaliile de interogare și persistență rămân localizate.

Stratul de integrare oferă comunicarea cu sisteme externe. NexusOps interacționează cu Proxmox pentru descoperire, provisioning și acțiuni controlate de lifecycle, cu SSH pentru execuții remote, cu Docker pentru deployment-uri Compose și cu sisteme de observabilitate precum Prometheus, Grafana și Loki pentru validarea readiness-ului. Acest strat are rolul de a ascunde diferențele dintre protocoale, API-uri și comenzi, expunând către logica de business o interfață operațională mai stabilă.

Stratul de securitate traversează întreaga aplicație. El include autentificarea prin tokenuri, autorizarea pe roluri, protecția credentialelor, redacția secretelor înainte de persistare, tokenurile scurte pentru remote access, rate limiting-ul și auditul. Acest strat nu este o componentă izolată, ci un set de reguli aplicate în toate fluxurile critice.

Interacțiunea dintre straturi poate fi descrisă ca un lanț controlat: frontend-ul trimite o cerere către API Layer, API Layer verifică accesul și transmite intenția către Business Logic Layer, acesta consultă Persistence Layer pentru starea curentă și folosește Integration Layer pentru operații externe. Rezultatul este persistat, iar frontend-ul primește o stare normalizată, nu rezultatul brut al infrastructurii.

[Figura 4.8 – Straturile arhitecturale ale backend-ului]

---

## 3. Domeniile funcționale ale backend-ului

Backend-ul este organizat în jurul unor domenii funcționale care reflectă responsabilitățile reale ale platformei. Această structură permite separarea logicii de business pe zone coerente, păstrând totodată un model comun de securitate, persistență și execuție.

Inventory Management există pentru a oferi sursa de adevăr a infrastructurii administrate. Acest domeniu păstrează serverele, mașinile virtuale, containerele, hypervisor-ele și hosturile fizice care pot fi administrate de NexusOps. Inventory include informații despre provider, stare de lifecycle, stare de management, metadate de sincronizare și date de conectare. Celelalte domenii nu execută operații pe IP-uri arbitrare, ci pe noduri cunoscute din Inventory.

Provisioning există pentru a crea noi noduri de infrastructură prin Proxmox și pentru a le introduce în modelul administrat al platformei. Responsabilitățile sale includ folosirea template-urilor, configurarea cloud-init, setarea rețelei, pornirea mașinii, așteptarea disponibilității SSH și înregistrarea rezultatului în Inventory. După înregistrare, provisioning-ul poate declanșa bootstrap prin Profiles, Packages sau Jobs.

Deployments există pentru a administra aplicații Docker Compose pe hosturi gestionate. Acest domeniu păstrează definițiile de deployment, țintele, execuțiile, reviziile și starea runtime observată. El interacționează cu Inventory pentru alegerea hosturilor, cu Credentials pentru secrete și credentiale de execuție și cu Jobs pentru rularea comenzilor pe hosturi.

Identity Management există pentru a orchestra identitatea Linux pe infrastructura administrată. Acest domeniu gestionează utilizatori Linux, grupuri, chei SSH, template-uri de permisiuni și replicarea acestor configurații pe hosturi. Este important de subliniat că Identity Management din NexusOps nu reprezintă autentificare centralizată de tip LDAP sau Active Directory. El este un mecanism de configurare și replicare operațională pe hosturi Linux.

Monitoring & Runtime există pentru a separa starea observată de procesul de randare al interfeței. Backend-ul păstrează snapshoturi de monitorizare, readiness, stări runtime și rezultate de refresh. Astfel, frontend-ul poate afișa stări coerente fără a declanșa la fiecare afișare apeluri live către Prometheus, Loki, Proxmox sau SSH.

Automation & Workflows există pentru a permite execuții recurente sau multi-pas. Automations definesc când și ce operație trebuie declanșată, iar Workflows oferă o cronologie persistentă pentru execuții compuse. Aceste domenii nu înlocuiesc Jobs, ci le folosesc pentru execuția efectivă. Astfel, operațiile rămân auditabile și corelate cu istoricul runtime.

Credential Management există pentru a proteja materialele sensibile. Credentialele pot reprezenta parole, chei SSH, tokenuri API sau secrete de mediu. Backend-ul stochează credentialele criptat și expune către frontend doar stări mascate. Valorile reale sunt rezolvate server-side numai în fluxurile de execuție care au nevoie de ele.

Remote Access există pentru acces interactiv controlat la hosturi administrate. Acest domeniu oferă shell WebSocket și operații SFTP prin backend, fără a expune direct credentialele sau conexiunile SSH către browser. Accesul remote este limitat la noduri din Inventory și folosește tokenuri scurte, scoped, diferite de tokenurile JWT obișnuite.

[Tabelul 4.4 – Domeniile funcționale ale backend-ului]

| Domeniu | Rol principal | Interacțiuni principale |
| --- | --- | --- |
| Inventory Management | Sursa de adevăr pentru nodurile administrate | Provisioning, Jobs, Deployments, Monitoring, Identity, Remote Access |
| Provisioning | Crearea și înregistrarea VM/LXC prin Proxmox | Proxmox, Inventory, Jobs, Profiles, Packages |
| Deployments | Administrarea aplicațiilor Docker Compose | Inventory, Jobs, Credentials, Runtime |
| Identity Management | Orchestrarea utilizatorilor și permisiunilor Linux | Inventory, Jobs, Credentials, Profiles |
| Monitoring & Runtime | Persistarea stării observate și readiness | Inventory, Integrations, Runtime Refresh |
| Automation & Workflows | Execuții programate și procese multi-pas | Jobs, Profiles, Packages, Deployments |
| Credential Management | Protejarea și rezolvarea secretelor | Inventory, Jobs, Deployments, Integrations, Identity |
| Remote Access | Acces interactiv controlat la hosturi | Inventory, Credentials, Security, Audit |

---

## 4. Mecanismul de execuție operațională

Mecanismul de execuție operațională este unul dintre cele mai importante elemente ale backend-ului NexusOps. Platforma nu tratează operațiile administrative ca simple comenzi izolate, ci ca acțiuni controlate, persistente și auditabile. În acest model, Jobs reprezintă unitatea atomică de execuție, iar Workflows oferă context pentru operații compuse.

Un Job descrie o execuție concretă asupra unui nod administrat. El păstrează ținta, tipul operației, comanda sau acțiunea executată, utilizatorul inițiator, starea execuției, outputul standard, erorile, codul de ieșire, timpii de execuție și metadatele de corelare. Jobs sunt folosite pentru comenzi raw, acțiuni operaționale, packages, profiles, deployment-uri și operații de identity. Această centralizare previne apariția mai multor mecanisme paralele de execuție și menține un istoric operațional uniform.

Workflows sunt folosite pentru a reprezenta operații care au mai mulți pași sau care provin dintr-un context mai larg, cum ar fi automatizările, aplicarea unui profil sau execuții programate. Un Workflow nu înlocuiește Job-ul, ci explică de ce a fost declanșată o execuție și cum se leagă mai multe execuții într-un proces. Din perspectivă arhitecturală, Jobs răspund la întrebarea „ce s-a executat pe host”, iar Workflows răspund la întrebarea „în ce proces operațional a avut loc execuția”.

Execuția remote se realizează în principal prin SSH. Backend-ul rezolvă nodul țintă din Inventory, verifică dacă acesta este administrabil, alege metoda de autentificare, rezolvă credentialele necesare și construiește comanda sau scriptul de rulat. Execuția propriu-zisă este realizată prin adaptorul SSH, iar rezultatele sunt persistate în Job. Frontend-ul nu primește acces direct la SSH și nu manipulează credentiale.

Modelul SSH este proiectat pentru control și trasabilitate. Credentialele pot proveni din metadatele nodului, dintr-o referință la Credential Manager sau dintr-un credential explicit de execuție/sudo. Atunci când operațiile includ valori sensibile, backend-ul persistă versiuni redacted ale comenzilor și outputurilor, astfel încât istoricul să fie util fără a expune secrete.

Operațiile runtime sunt tratate ca stări persistente, nu ca rezultate volatile ale unor apeluri live. De exemplu, deployment-urile Docker Compose pot avea stări precum running, degraded, stopped sau failed, iar aceste stări sunt actualizate prin operații explicite de refresh. Monitoring-ul și readiness-ul folosesc snapshoturi persistente, astfel încât interfața să poată afișa stări coerente fără a suprasolicita sistemele externe.

Fluxul unei operațiuni inițiate de utilizator poate fi descris astfel: utilizatorul alege o acțiune în frontend; frontend-ul trimite cererea către backend; backend-ul autentifică utilizatorul și verifică rolul; serviciul de business validează ținta din Inventory; credentialele necesare sunt rezolvate server-side; se creează un Job sau un Workflow; adaptorul potrivit execută operația asupra infrastructurii; rezultatul este persistat; frontend-ul citește starea normalizată și o afișează operatorului.

Această arhitectură oferă un flux clar de orchestrare: intenție, validare, rezolvare de context, execuție, persistare și observabilitate. Ea este potrivită pentru o platformă de administrare infrastructură deoarece reduce riscul ca operațiile să fie executate necontrolat și oferă o evidență completă a activităților administrative.

[Figura 4.9 – Fluxul unei operațiuni administrative]

[Figura 4.10 – Modelul Jobs și Workflows]

---

## 5. Arhitectura de securitate

Arhitectura de securitate a backend-ului NexusOps este proiectată în jurul ideii că toate operațiile administrative trebuie controlate de server, nu de browser. Backend-ul autentifică utilizatorii, aplică autorizarea pe roluri, protejează credentialele, limitează expunerea tokenurilor și păstrează urme de audit pentru acțiunile importante.

Autentificarea se bazează pe utilizatori locali ai platformei NexusOps. Utilizatorii se autentifică prin username sau email și parolă, iar backend-ul emite tokenuri de acces și refresh. Parolele sunt stocate ca hash-uri, nu ca valori plaintext. Tokenurile de acces sunt scurte ca durată de viață, iar tokenurile de refresh sunt persistate ca sesiuni hash-uite și se rotesc la fiecare refresh. Acest model permite revocarea sesiunilor, detectarea reutilizării unui refresh token revocat și separarea între autentificarea curentă și sesiunile pe termen mai lung.

Autorizarea este realizată prin RBAC, cu roluri precum admin, operator și viewer. Rolul viewer este potrivit pentru citirea stării și observabilitate, operatorul poate declanșa operații administrative, iar adminul are acces la zone sensibile precum credentiale, utilizatori, integrări și audit. Această împărțire reflectă responsabilitățile reale dintr-o platformă de administrare infrastructură.

JWT este folosit ca mecanism de transport al identității autentificate pentru cererile obișnuite ale frontend-ului. Totuși, backend-ul nu folosește același model pentru toate tipurile de acces. Pentru remote shell WebSocket, NexusOps folosește tokenuri scurte, one-time, scoped la utilizator, server, operație, rol și sesiune. Această decizie reduce riscul expunerii unui token de autentificare cu durată mai mare în URL-uri WebSocket.

Credential protection este un principiu central. Credentialele sunt stocate criptat și nu sunt returnate de API în formă decriptată. Frontend-ul vede doar metadate și valori mascate. Decriptarea are loc doar în backend, în momentul unei operații care necesită efectiv credentialul. În plus, valorile sensibile sunt redactate înainte de a fi persistate în istoricul Jobs, Workflows, Deployments sau Audit.

Auditabilitatea este susținută prin evenimente de audit, istoric de Jobs, execuții de deployment, Workflows și metadate de corelare. Sistemul poate explica cine a inițiat o operație, asupra cărui nod, cu ce rezultat și în ce context operațional. Această caracteristică este esențială într-o platformă care execută acțiuni administrative asupra infrastructurii.

Principiile de execuție securizată includ limitarea operațiilor la noduri din Inventory, rezolvarea credentialelor doar server-side, redacția secretelor, validarea tranzițiilor de stare, verificări de comandă pentru valori interpolate și separarea accesului interactiv de mecanismul Jobs. De asemenea, backend-ul include guardrails de producție, precum blocarea pornirii cu setări nesigure, rate limiting și headere de securitate.

[Figura 4.11 – Modelul de securitate al backend-ului]

---

## 6. Integrarea cu sisteme externe

Backend-ul NexusOps integrează mai multe sisteme externe, fiecare având un rol operațional distinct. Integrarea nu este realizată direct din frontend, ci prin servicii și adaptoare backend, ceea ce permite control, normalizare și audit.

Proxmox este folosit ca provider de infrastructură pentru vizibilitate, descoperire, import în Inventory, acțiuni controlate de lifecycle și provisioning bazat pe template-uri. Comunicarea se realizează prin API-ul Proxmox. Informațiile schimbate includ noduri cluster, VM-uri, containere, storage, statusuri, task-uri și metadate de provider. Rolul operațional al Proxmox este să furnizeze infrastructura de virtualizare, în timp ce NexusOps păstrează controlul orchestrat prin Inventory.

SSH este mecanismul principal pentru execuție remote pe hosturi Linux. Comunicarea se realizează din backend către hostul țintă, folosind metadatele Inventory și credentialele rezolvate server-side. Prin SSH sunt executate comenzi, acțiuni operaționale, packages, profile steps, deployment commands și operații de identity. SSH este canalul prin care intenția operatorului ajunge efectiv la nodul de infrastructură.

Docker este folosit în special pentru deployment-uri Docker Compose și pentru inspecția runtime a containerelor. Backend-ul nu tratează Docker ca o platformă separată de orchestrare, ci ca un runtime disponibil pe hosturi gestionate. Comenzile Docker sunt executate prin Jobs și SSH, iar rezultatele sunt persistate ca stare de deployment, runtime status și diagnostic operațional.

Grafana are rolul de interfață dedicată pentru observabilitate avansată. NexusOps nu recreează dashboard-uri Grafana și nu încorporează panouri Grafana ca sursă principală de date. Backend-ul poate păstra linkuri și configurații care permit operatorilor să ajungă rapid în Grafana pentru analiză detaliată.

Prometheus este folosit pentru validarea disponibilității infrastructurii de monitorizare și pentru verificări de readiness. Backend-ul tratează Prometheus ca provider de observabilitate, nu ca sursă care trebuie interogată intens la fiecare randare de pagină. Rezultatele relevante sunt persistate în snapshoturi, iar starea este citită ulterior din baza de date.

Loki este asociat cu verificarea disponibilității logurilor și cu integrarea observabilității. Ca și în cazul Prometheus, NexusOps evită ca randarea obișnuită a paginilor să depindă de interogări live către Loki. Rolul său este de provider de loguri, iar backend-ul păstrează o reprezentare operațională a readiness-ului.

Tailscale are rol de rețea privată și conectivitate sigură pentru medii self-hosted sau expuneri controlate. În arhitectura backend-ului, Tailscale este relevant mai ales pentru accesul securizat la platformă și la infrastructură, nu ca sistem principal de orchestrare. Backend-ul include măsuri de hardening utile pentru expuneri controlate, precum rate limiting și headere de securitate.

[Tabelul 4.5 – Integrările backend-ului]

| Sistem extern | Scop | Model de comunicare | Informații schimbate | Rol operațional |
| --- | --- | --- | --- | --- |
| Proxmox | Virtualizare, discovery și provisioning | API HTTP către Proxmox | Noduri, VM/LXC, storage, statusuri, task-uri | Provider de infrastructură |
| SSH | Execuție remote pe hosturi Linux | Conexiune SSH inițiată de backend | Comenzi, stdout, stderr, exit code | Canal principal de execuție |
| Docker | Runtime pentru aplicații Compose | Comenzi Docker prin SSH/Jobs | Stare containere, logs, compose operations | Execuție și diagnostic deployment |
| Grafana | Observabilitate vizuală | Linkuri și configurații persistate | URL-uri, dashboard paths, metadate nod | Analiză externă detaliată |
| Prometheus | Health și readiness monitoring | Verificări controlate prin backend | Provider health, targets, exporter availability | Validare monitoring |
| Loki | Validarea disponibilității logurilor | Verificări controlate prin backend | Stare provider, stream availability | Validare logging |
| Tailscale | Conectivitate privată și acces controlat | Rețea securizată pentru acces | Metadate de conectivitate și expunere | Acces sigur în medii self-hosted |

---

## 7. Principii arhitecturale

Modularitatea este principiul prin care backend-ul este împărțit în domenii funcționale clare. Inventory, Jobs, Credentials, Provisioning, Deployments, Identity, Monitoring și Automations pot evolua separat ca logică, dar rămân integrate într-o singură aplicație coerentă. Această abordare oferă simplitatea operațională a unui monolit și disciplina internă a unei arhitecturi modulare.

Separation of concerns este aplicată prin separarea stratului API de logica de business, a logicii de business de persistență și a integrărilor externe de regulile domeniului. Această separare face sistemul mai ușor de întreținut și reduce riscul ca modificările într-un provider extern să afecteze întreaga platformă.

Inventory-centric architecture este principiul central al NexusOps. Infrastructura administrată este reprezentată prin Inventory, iar operațiile se execută numai asupra acestor ținte. Această decizie oferă control, trasabilitate și coerență între provisioning, monitoring, deployment, identity și remote access.

Reusability apare prin definirea de Packages, Profiles, Actions și Blueprints. Aceste concepte permit reutilizarea unor operații și configurații fără a duplica logica de execuție. Toate se rezolvă în final către Jobs, ceea ce păstrează mecanismul de execuție uniform.

Auditability este obținută prin persistarea execuțiilor, stărilor, outputurilor redacted, workflow-urilor și evenimentelor administrative. Backend-ul nu execută operații importante fără a păstra contextul și rezultatul.

Extensibility este susținută prin adaptoare, domenii funcționale și contracte persistente. Noi provider-e, noi tipuri de acțiuni sau noi fluxuri de orchestration pot fi adăugate fără a schimba principiile de bază: Inventory ca țintă, Jobs ca execuție, Credentials ca rezolvare securizată a secretelor.

Scalability considerations sunt tratate pragmatic. Implementarea curentă folosește un scheduler și o coadă async în proces, fără a introduce încă un sistem distribuit de workers. Această alegere este adecvată pentru stadiul aplicației și pentru obiectivul de simplitate operațională. În același timp, existența Workflows, snapshoturilor runtime, metadatelor de execuție și markerelor de stare pregătește arhitectura pentru extindere ulterioară către workers distribuiți, streaming sau mecanisme mai avansate de orchestration.

[Tabelul 4.6 – Principiile arhitecturale ale backend-ului]

| Principiu | Aplicare în NexusOps | Beneficiu |
| --- | --- | --- |
| Modularity | Domenii backend separate într-un modular monolith | Organizare clară și evoluție controlată |
| Separation of concerns | API, business logic, persistence, integrations și security separate | Mentenabilitate și testabilitate |
| Inventory-centric architecture | Operațiile vizează noduri administrate din Inventory | Control și trasabilitate |
| Reusability | Packages, Profiles, Actions, Blueprints | Reducerea duplicării operaționale |
| Auditability | Jobs, Workflows, Audit Events, Deployment Executions | Evidență completă a operațiilor |
| Extensibility | Adaptoare și domenii funcționale | Posibilitatea adăugării de noi integrări |
| Scalability considerations | Snapshoturi, workflow metadata, scheduler in-process | Bază pentru extindere graduală |

---

## 8. Concluzii

Backend-ul NexusOps a fost proiectat ca un plan de control centralizat pentru administrarea infrastructurii Linux. Alegerea unei arhitecturi de tip modular monolith permite menținerea unui sistem ușor de rulat și dezvoltat, dar suficient de structurat pentru a separa responsabilitățile pe domenii operaționale.

Beneficiul principal al acestei arhitecturi este coerența. Toate operațiile importante trec prin aceleași principii: utilizator autentificat, autorizare pe roluri, țintă din Inventory, credentiale rezolvate server-side, execuție prin Jobs, rezultat persistent și auditabil. Această uniformitate reduce riscul operațional și face platforma mai ușor de explicat, testat și extins.

Backend-ul susține obiectivele NexusOps prin faptul că transformă operațiile administrative manuale în fluxuri controlate și reutilizabile. Provisioning-ul, deployment-urile, identitatea Linux, monitorizarea, remote access-ul și automatizările nu sunt funcții izolate, ci domenii care folosesc aceeași fundație arhitecturală. Astfel, NexusOps poate funcționa ca o platformă unitară de orchestrare, capabilă să ofere vizibilitate, control, securitate și trasabilitate asupra infrastructurii administrate.
