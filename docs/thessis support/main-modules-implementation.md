# 4.7 Implementarea modulelor principale

Acest document oferă material explicativ pentru redactarea capitolului **4.7 Implementarea modulelor principale** din lucrarea de licență. Textul este scris ca suport academic și arhitectural, nu ca documentație de cod. Scopul său este să explice rolul fiecărui modul, responsabilitățile sale, relațiile cu celelalte domenii și elementele care pot fi transformate ulterior în text final pentru teză.

Observație privind numerotarea: în captura inițială, secțiunea **4.7.4** apare de două ori, pentru **Monitoring & Runtime** și **Identity Management**. Pentru consistență, se recomandă următoarea numerotare:

- 4.7.1 Inventory Management
- 4.7.2 Provisioning
- 4.7.3 Deployments
- 4.7.4 Monitoring & Runtime
- 4.7.5 Identity Management
- 4.7.6 Automation & Workflows
- 4.7.7 Credential Manager
- 4.7.8 Remote Access

[Figura 4.15 – Structura modulelor principale NexusOps]

## 4.7.1 Inventory Management

Modulul **Inventory Management** reprezintă fundamentul operațional al platformei NexusOps. El funcționează ca sursă de adevăr pentru nodurile administrate, incluzând mașini virtuale, containere LXC, hosturi fizice și hypervisor-e. În loc ca platforma să execute operații pe adrese IP introduse arbitrar, toate modulele importante folosesc noduri înregistrate în Inventory.

Din punct de vedere arhitectural, Inventory are rol de CMDB operațional. Fiecare nod administrat conține informații despre identitate, stare, provider, lifecycle, conectivitate și metadate de sincronizare. Astfel, Inventory nu este doar o listă de servere, ci un model coerent prin care NexusOps înțelege ce infrastructură controlează și ce operații sunt permise asupra fiecărui nod.

Modulul este folosit de aproape toate celelalte domenii. Jobs execută comenzi asupra nodurilor din Inventory, Deployments aleg hosturi țintă din Inventory, Provisioning creează noduri care sunt apoi înregistrate în Inventory, Monitoring citește starea nodurilor administrate, Identity replică utilizatori și grupuri pe hosturi Inventory, iar Remote Access permite acces interactiv doar către noduri administrate.

Interfața frontend pentru Inventory pune accent pe vizibilitate operațională. Utilizatorul poate consulta nodurile, starea lor, readiness-ul SSH, starea runtime, metadatele Proxmox, badge-urile de lifecycle și avertismentele relevante. De asemenea, interfața permite importul manual al hosturilor existente, editarea metadatelor și accesul către pagini de detaliu.

[Figura 4.16 – Rolul Inventory ca sursă de adevăr pentru operații]

| Aspect | Descriere |
| --- | --- |
| Scop | Catalog central al infrastructurii administrate |
| Entități principale | Server / Inventory Node, stări lifecycle, metadate provider, runtime state |
| Utilizatori principali | Operator, administrator, viewer |
| Module dependente | Jobs, Provisioning, Deployments, Monitoring, Identity, Remote Access |
| Beneficiu arhitectural | Oferă control, trasabilitate și elimină operațiile pe ținte necunoscute |

Flux operațional recomandat pentru teză:

```text
Provider discovery / Import manual / Provisioning
        -> Inventory record
        -> target administrabil
        -> Jobs / Deployments / Identity / Monitoring / Remote Access
```

## 4.7.2 Provisioning

Modulul **Provisioning** permite crearea controlată a infrastructurii noi prin Proxmox. În implementarea NexusOps, provisioning-ul este bazat pe template-uri și cloud-init, nu pe instalări ISO sau proceduri manuale. Această decizie reduce complexitatea și face procesul repetabil.

Provisioning-ul gestionează parametri precum template-ul, nodul Proxmox țintă, CPU, memorie, discuri, rețea, gateway, DNS, utilizator cloud-init, chei SSH și adrese IP statice. Pentru scenarii repetabile, platforma oferă blueprint-uri de provisioning. Acestea păstrează valorile comune, dar lasă utilizatorului control asupra valorilor unice pentru fiecare mașină, cum ar fi numele VM-ului, hostname-ul, VMID-ul sau IP-ul.

Un aspect important al implementării este ordinea operațiilor. NexusOps creează VM-ul sau containerul, configurează sistemul, pornește instanța, așteaptă disponibilitatea SSH și abia apoi înregistrează nodul în Inventory. După înregistrare, pot fi declanșate acțiuni de bootstrap, precum aplicarea unui profil, instalarea unor package-uri sau rularea unor Jobs. Această ordine păstrează Inventory ca graniță arhitecturală pentru operațiile ulterioare.

Frontend-ul pentru Provisioning este construit ca un workspace operațional. În loc să afișeze permanent toate formularele, interfața organizează setările avansate în secțiuni, drawer-e și panouri. Utilizatorul poate selecta blueprint-uri, configura resurse, alege template-uri și defini planuri de bootstrap.

[Figura 4.17 – Fluxul de provisioning în NexusOps]

| Aspect | Descriere |
| --- | --- |
| Scop | Crearea VM/LXC prin Proxmox și înregistrarea în Inventory |
| Intrări principale | Template, resurse, rețea, cloud-init, bootstrap plan |
| Ieșiri principale | Nod Proxmox creat, Inventory record, Jobs de bootstrap |
| Integrare externă | Proxmox API |
| Relații interne | Inventory, Jobs, Packages, Profiles, Deployments |

Flux operațional recomandat pentru teză:

```text
Blueprint / formular provisioning
        -> Proxmox clone/create
        -> cloud-init și rețea
        -> pornire VM/LXC
        -> verificare SSH
        -> înregistrare Inventory
        -> bootstrap prin Jobs/Profile/Package
```

## 4.7.3 Deployments

Modulul **Deployments** gestionează aplicații Docker Compose rulate pe hosturi administrate. Scopul său este să ofere operatorilor un mod controlat de a defini, lansa, reporni, opri și inspecta servicii containerizate fără a se conecta manual pe fiecare server.

Un deployment păstrează definiția Docker Compose, variabilele de mediu non-secrete, referințele către credentiale pentru secrete, credentialul de execuție/sudo și lista de hosturi țintă. Această separare este importantă: secretele aplicației sunt tratate diferit față de credentialul folosit pentru executarea comenzilor pe host.

Execuția deployment-urilor nu introduce un mecanism separat de remote execution. Operațiile precum deploy, redeploy, restart, stop, status, logs și runtime refresh sunt transformate în Jobs și executate prin SSH pe hosturile din Inventory. Astfel, deployment-urile beneficiază de același model de audit, output, status și redacție a secretelor ca restul platformei.

Interfața frontend este proiectată ca un dashboard de servicii. Deployment-urile apar sub formă de carduri operaționale care afișează stare runtime, health, sync, ținte, porturi, durată, execuții recente, output și erori. Utilizatorul poate previzualiza comenzile generate și validarea Compose înainte de execuție, ceea ce reduce riscul de configurare greșită.

[Figura 4.18 – Arhitectura modulului Deployments]

| Aspect | Descriere |
| --- | --- |
| Scop | Administrarea aplicațiilor Docker Compose pe hosturi Inventory |
| Date gestionate | Compose content, env, credential refs, targets, executions, runtime state |
| Execuție | Prin Jobs și SSH |
| Interacțiuni frontend | create/edit, preview, deploy, redeploy, restart, stop, logs, inspect |
| Beneficiu | Unifică deployment-ul aplicațiilor cu auditul și inventarul platformei |

Flux operațional recomandat pentru teză:

```text
Deployment definition
        -> target Inventory host(s)
        -> credential resolution
        -> Job per target
        -> Docker Compose command
        -> runtime state persisted
        -> dashboard feedback
```

## 4.7.4 Monitoring & Runtime

Modulul **Monitoring & Runtime** oferă vizibilitate asupra stării operaționale a nodurilor și serviciilor administrate. NexusOps nu încearcă să înlocuiască Prometheus, Loki sau Grafana, ci să ofere o vedere de readiness și diagnostic rapid asupra infrastructurii gestionate.

Principiul central al acestui modul este utilizarea snapshoturilor persistente. În loc ca frontend-ul să declanșeze interogări live către Prometheus, Loki, Grafana, Proxmox sau SSH la fiecare afișare, backend-ul păstrează stări runtime și monitoring în baza de date. Interfața citește aceste stări și le afișează sub formă de badge-uri, carduri și motive de degradare.

Monitoring verifică disponibilitatea componentelor precum node_exporter, promtail sau cAdvisor, precum și starea providerilor de observabilitate. Grafana este tratat ca instrument extern de analiză detaliată, nu ca dashboard generat sau controlat de NexusOps. Prometheus și Loki sunt folosite ca provider-e de observabilitate, iar NexusOps păstrează o reprezentare operațională a rezultatelor.

Runtime state este folosit nu doar pentru monitoring, ci și pentru Inventory, Deployments și Host Detail. De exemplu, un nod poate avea stări despre readiness SSH, provider state, orchestration state, monitoring state, stale reasons sau degraded reasons. Această abordare ajută operatorul să înțeleagă rapid dacă un nod este pregătit pentru execuții, dacă este degradat sau dacă datele sunt stale.

[Figura 4.19 – Modelul snapshot pentru Monitoring & Runtime]

| Aspect | Descriere |
| --- | --- |
| Scop | Vizibilitate operațională și readiness pentru noduri și servicii |
| Date afișate | Monitoring state, runtime state, exporter status, stale/degraded reasons |
| Integrare externă | Prometheus, Loki, Grafana, SSH checks |
| Model de actualizare | Refresh explicit sau programat, apoi citire din snapshoturi |
| Beneficiu | Evită interogările live costisitoare în timpul randării interfeței |

Flux operațional recomandat pentru teză:

```text
Refresh monitoring/runtime
        -> verificări backend
        -> snapshot persistent
        -> frontend citește starea normalizată
        -> operator vede readiness și motive de degradare
```

## 4.7.5 Identity Management

Modulul **Identity Management** gestionează identitatea Linux pe hosturile administrate. El nu reprezintă autentificare centralizată pentru platformă și nu implementează LDAP, Active Directory, Kerberos sau SSO. Scopul său este configurarea și replicarea utilizatorilor, grupurilor, cheilor SSH și permisiunilor pe infrastructura Linux gestionată de NexusOps.

Modulul permite definirea de utilizatori Linux, grupuri, membri, chei SSH și template-uri de permisiuni. Aceste înregistrări pot exista ca stare dorită înainte de replicarea pe hosturi reale. Atunci când utilizatorul decide să aplice această stare pe infrastructură, backend-ul transformă operațiile în Jobs executate prin SSH.

Un aspect important este separarea dintre parola contului Linux și credentialul de execuție/sudo. Parola care trebuie setată pentru un utilizator Linux poate fi referită prin Credential Manager, în timp ce credentialul folosit pentru a executa operația pe host poate fi diferit. Această separare reduce confuzia și susține un model mai sigur de operare.

Frontend-ul Identity este proiectat ca o interfață ghidată. El include access profiles, preseturi pentru grupuri operaționale, preseturi de permisiuni și controale avansate pentru utilizatori tehnici. Interfața permite descoperirea utilizatorilor și grupurilor existente pe hosturi, adoptarea lor în starea administrată și replicarea pe mai multe ținte.

[Figura 4.20 – Fluxul Identity Management prin Jobs]

| Aspect | Descriere |
| --- | --- |
| Scop | Orchestrarea utilizatorilor, grupurilor, cheilor SSH și permisiunilor Linux |
| Entități principale | Linux User, Linux Group, SSH Key, Permission Template |
| Execuție | Prin Jobs și SSH |
| Integrare cu Credential Manager | Parole de cont și credentiale de execuție/sudo |
| Limitare intenționată | Nu este sistem de autentificare centralizată LDAP/SSO |

Flux operațional recomandat pentru teză:

```text
Managed Identity record
        -> target Inventory hosts
        -> optional credential refs
        -> Identity replication request
        -> Jobs fanout
        -> SSH commands
        -> per-host result
```

## 4.7.6 Automation & Workflows

Modulul **Automation & Workflows** oferă mecanisme pentru execuții programate, procese multi-pas și vizibilitate asupra operațiilor compuse. În NexusOps, Automation și Workflows nu înlocuiesc Jobs, ci le folosesc ca unitate de execuție.

Automations definesc reguli de declanșare, cum ar fi intervale sau expresii cron, și operații care trebuie executate: acțiuni predefinite, comenzi, packages, profiles sau deployment-uri. Ele sunt utile pentru sarcini recurente, precum verificări periodice, operații de mentenanță sau aplicarea unor configurații standardizate.

Workflows oferă o cronologie persistentă pentru operații care implică mai mulți pași. Un workflow poate explica ce proces a declanșat joburile, ce pași au fost executați, ce pas a eșuat și ce rezultat final a fost obținut. Din punct de vedere arhitectural, Jobs explică execuția concretă, iar Workflows explică procesul operațional.

Frontend-ul pentru Automations afișează carduri cu stare runtime, următoarea execuție, ultima execuție, durată și rezultate recente. Workflows afișează timeline-uri, pași, loguri și legături către joburile asociate. Această vizibilitate este importantă pentru troubleshooting și audit.

[Figura 4.21 – Relația dintre Automations, Workflows și Jobs]

| Aspect | Descriere |
| --- | --- |
| Scop | Execuții programate și vizibilitate asupra proceselor multi-pas |
| Automation | Definește când și ce se execută |
| Workflow | Explică pașii și progresul procesului |
| Job | Execută operația concretă pe host |
| Beneficiu | Separă programarea, orchestration-ul și execuția efectivă |

Flux operațional recomandat pentru teză:

```text
Automation schedule / manual run
        -> WorkflowRun
        -> WorkflowStep(s)
        -> Job/Profile/Package/Deployment execution
        -> persisted runtime result
        -> frontend timeline
```

## 4.7.7 Credential Manager

Modulul **Credential Manager** gestionează materialele sensibile folosite de platformă. El permite stocarea de parole, parole SSH, chei SSH, tokenuri API și secrete de mediu. Scopul său este să evite copierea secretelor în formulare, joburi, deployment-uri sau fișiere de configurare.

Credentialele sunt stocate criptat în backend și nu sunt returnate către frontend în formă decriptată. Interfața afișează doar metadate, tipul credentialului, scope-ul și o reprezentare mascată. Secretul poate fi trimis la creare sau înlocuire, dar nu este afișat ulterior. Această abordare este importantă pentru protecția datelor sensibile.

Credential Manager este folosit de mai multe module. Inventory poate referi credentiale pentru SSH, Jobs pot folosi credentiale de execuție sau sudo, Deployments pot folosi credentiale pentru env secrets și execuție, Integrations pot folosi tokenuri provider, Identity poate folosi credentiale pentru parole de cont, iar Packages/Profiles pot folosi credentiale pentru variabile sensibile.

Un alt aspect important este ciclul de viață al credentialelor. Ștergerea poate fi recuperabilă, iar purge-ul permanent trebuie controlat atunci când alte entități încă referă credentialul. Astfel, platforma reduce riscul de a rupe accidental fluxuri operaționale existente.

[Figura 4.22 – Credential Manager ca serviciu comun pentru module]

| Aspect | Descriere |
| --- | --- |
| Scop | Stocarea securizată și reutilizabilă a secretelor |
| Tipuri de secrete | Password, SSH password, SSH key, API token, env secret |
| Consumatori | Inventory, Jobs, Deployments, Identity, Integrations, Packages, Profiles |
| Principiu de securitate | Frontend-ul vede referințe și valori mascate, backend-ul rezolvă secretul |
| Beneficiu | Reduce expunerea secretelor și duplicarea acestora |

Flux operațional recomandat pentru teză:

```text
Credential creat de admin
        -> referință selectată în modul operațional
        -> backend rezolvă secretul la runtime
        -> comandă executată în memorie
        -> istoric redacted persistat
```

## 4.7.8 Remote Access

Modulul **Remote Access** oferă acces interactiv controlat la hosturile administrate. El include shell în browser și operații de fișiere prin SFTP, precum listare directoare, citire fișiere și scriere controlată. Scopul său este să ofere operatorilor un instrument integrat pentru intervenții rapide, fără a expune credentiale sau conexiuni SSH directe către browser.

Remote Access respectă granița Inventory. Utilizatorul poate accesa doar hosturi administrate, nu adrese arbitrare. Backend-ul verifică rolul utilizatorului, starea nodului, credentialele disponibile și regulile de acces. Pentru shell, frontend-ul cere mai întâi un token scurt, scoped pentru host și operație, apoi deschide conexiunea WebSocket. Astfel, tokenul JWT principal nu este folosit direct în URL-ul WebSocket.

Shell-ul interactiv este separat de Jobs. Comenzile tastate în shell nu sunt persistate ca Jobs, deoarece shell-ul este o sesiune interactivă. În schimb, operațiile automate, packages, profiles, deployments și identity continuă să folosească Jobs. Această separare este importantă pentru a diferenția intervenția manuală de execuțiile operaționale auditabile.

Frontend-ul Remote Access este organizat ca un workspace Host Tools. El include browser de fișiere, editor și terminal persistent. Interfața afișează starea conexiunii, permite conectarea/deconectarea și respectă limitările de rol. Pentru scrierea fișierelor, platforma folosește mecanisme controlate, precum verificarea hash-ului, pentru a reduce riscul suprascrierilor accidentale.

[Figura 4.23 – Fluxul Remote Access cu token scoped și WebSocket]

| Aspect | Descriere |
| --- | --- |
| Scop | Acces interactiv la hosturi administrate |
| Funcții principale | Shell WebSocket, SFTP browse/read/write |
| Graniță arhitecturală | Doar Inventory-managed hosts |
| Securitate | Token scurt scoped pentru shell, RBAC, credentiale rezolvate server-side |
| Diferență față de Jobs | Shell-ul este interactiv; Jobs sunt execuții persistente și auditabile |

Flux operațional recomandat pentru teză:

```text
Host Tools page
        -> request scoped shell token
        -> WebSocket shell session
        -> backend SSH channel
        -> managed host
```

## Tabel sintetic pentru capitol

| Secțiune | Modul | Rol în platformă | Dependență principală | Tip de interacțiune |
| --- | --- | --- | --- | --- |
| 4.7.1 | Inventory Management | Sursa de adevăr pentru noduri | PostgreSQL, Proxmox metadata | CRUD, import, lifecycle, readiness |
| 4.7.2 | Provisioning | Creare VM/LXC | Proxmox, Inventory | Template clone/create, cloud-init, bootstrap |
| 4.7.3 | Deployments | Administrare Docker Compose | Inventory, Jobs, Credentials | Deploy/redeploy/restart/stop/status/logs |
| 4.7.4 | Monitoring & Runtime | Vizibilitate operațională | Snapshots, Prometheus/Loki/Grafana | Readiness, refresh, diagnostic |
| 4.7.5 | Identity Management | Orchestrare identitate Linux | Inventory, Jobs, Credentials | User/group/SSH key/permissions replication |
| 4.7.6 | Automation & Workflows | Procese recurente și multi-pas | Jobs, Profiles, Packages, Deployments | Scheduling, timeline, status |
| 4.7.7 | Credential Manager | Protecția secretelor | Encryption, Credential references | Secret storage, masked display, runtime resolution |
| 4.7.8 | Remote Access | Acces interactiv la hosturi | Inventory, SSH, scoped tokens | Shell WebSocket, SFTP files |

## Figuri recomandate pentru capitol

| Figură | Titlu recomandat | Conținut |
| --- | --- | --- |
| Figura 4.15 | Structura modulelor principale NexusOps | Diagramă cu modulele și relațiile lor |
| Figura 4.16 | Rolul Inventory ca sursă de adevăr | Inventory în centru, modulele dependente în jur |
| Figura 4.17 | Fluxul de provisioning | Blueprint -> Proxmox -> Inventory -> Bootstrap |
| Figura 4.18 | Arhitectura Deployments | Deployment definition -> targets -> Jobs -> Docker |
| Figura 4.19 | Modelul snapshot Monitoring & Runtime | Refresh backend -> snapshot DB -> frontend |
| Figura 4.20 | Fluxul Identity Management | Identity desired state -> Jobs -> hosturi Linux |
| Figura 4.21 | Automations, Workflows și Jobs | Automation -> Workflow -> Jobs |
| Figura 4.22 | Credential Manager ca serviciu comun | Credentiale referite de module diferite |
| Figura 4.23 | Remote Access | Frontend -> scoped token -> WebSocket -> backend SSH |

## Observații pentru redactarea finală

Pentru textul final al tezei, fiecare subcapitol poate urma aceeași structură:

1. descrierea scopului modulului;
2. rolul în arhitectura NexusOps;
3. entități și informații gestionate;
4. interacțiunea cu backend, frontend și baza de date;
5. relația cu Inventory, Jobs și Credential Manager;
6. beneficii operaționale;
7. limitări intenționate sau decizii de proiectare.

Această structură păstrează capitolul coerent și evită transformarea lui într-o listă de endpointuri sau fișiere sursă.
