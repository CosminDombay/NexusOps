# Capitolul 5: Validarea și utilizarea platformei

Acest document oferă material sursă pentru capitolul **Validarea și utilizarea platformei**. Conținutul este formulat în limbaj academic și se concentrează pe funcționalitățile implementate efectiv în NexusOps, pe fluxurile operaționale validate, pe mediul de testare și pe limitările reale ale platformei la momentul redactării.

# 5.7 Mediul de testare

Mediul de testare NexusOps a fost construit pentru a valida comportamentul platformei într-un context apropiat de utilizarea reală: infrastructură virtualizată prin Proxmox, noduri Linux administrabile prin SSH, servicii Docker Compose, persistență PostgreSQL și o interfață web accesată din browser. Obiectivul mediului nu a fost doar verificarea izolată a funcțiilor, ci demonstrarea unui flux complet de administrare: descoperirea infrastructurii, înregistrarea în Inventory, execuția de joburi, aplicarea de pachete și profile, deployment-ul de servicii și validarea stării finale.

Infrastructura Proxmox a fost folosită ca provider principal pentru vizibilitate, descoperire și provisioning. NexusOps se conectează la Proxmox pentru a lista noduri, mașini virtuale, containere LXC, storage și stări de lifecycle. În procesul de testare, Proxmox a avut rolul de strat de infrastructură reală, iar NexusOps a avut rolul de control plane care importă, reconciliază sau provision-ează resursele, fără a transforma direct fiecare resursă descoperită într-o țintă administrată.

Mașinile virtuale de test au fost folosite pentru validarea scenariilor de provisioning, Inventory, Jobs, Packages, Profiles, Deployments și Identity. Planul de demonstrație curent folosește un host Ubuntu Server 24.04 LTS, denumit `test`, cu aproximativ 4 GB RAM, disc de sistem de 35 GB și, opțional, un disc de date de 100 GB. Acest host este folosit pentru demonstrarea unui Docker demo host: instalarea utilitarelor de bază, instalarea Docker Engine, configurarea utilizatorului `cerberus` în grupul `docker`, deployment-ul Portainer, cAdvisor și al unui serviciu Nginx demonstrativ.

Containerele LXC au fost incluse în aria de testare pentru descoperire, lifecycle și provisioning de bază. Implementarea suportă descoperirea LXC, sincronizarea statusului, importul sau înregistrarea în Inventory și cereri de provisioning LXC prin Proxmox. Pentru LXC, platforma separă existența provider-side de readiness-ul SSH, deoarece un container poate fi pornit și vizibil în Proxmox fără să fie încă pregătit pentru execuții SSH.

Sistemele Linux folosite în testare sunt relevante deoarece NexusOps este orientat spre administrarea hosturilor Linux. Ubuntu Server 24.04 LTS este sistemul de operare principal în scenariul demonstrativ, iar logica Identity include abstractizări pentru diferențe între distribuții, cum ar fi grupurile `sudo` și `wheel`. Validarea efectivă a operațiilor se realizează prin SSH, Jobs și comenzi executate pe hosturi Inventory-managed.

Hosturile Docker au fost utilizate pentru validarea deployment-urilor Docker Compose și a fluxului de aplicație demonstrativă. Docker Engine, Docker Compose plugin, Portainer, cAdvisor și Nginx demonstrativ formează un scenariu compact, vizibil și ușor de explicat. Acest scenariu verifică nu doar instalarea software-ului, ci și capacitatea NexusOps de a orchestra o mașină de la stadiul de nod administrat până la rularea unei aplicații containerizate.

Stack-ul de monitorizare este tratat în NexusOps ca strat extern de observabilitate. Platforma include integrare cu Prometheus, Grafana și Loki la nivel de readiness, validare și linkuri de acces, însă nu încearcă să înlocuiască aceste sisteme. Monitoring-ul NexusOps validează stări precum disponibilitatea exporterelor, staleness, sănătatea providerului și linkuri Grafana configurate. Pentru primul flux demonstrativ, monitorizarea extinsă nu este obligatorie, dar funcționalitatea există în platformă și poate fi documentată ca suprafață implementată.

Tailscale apare în platformă ca opțiune de integrare și pachet operațional, utilă pentru conectivitate privată în medii self-hosted. În scenariul demonstrativ simplificat, Tailscale este în afara fluxului principal, pentru a reduce riscul de dependențe externe în prezentare. Totuși, existența pachetului și a suprafeței de configurare arată că platforma a fost proiectată pentru medii în care accesul securizat prin rețea privată poate deveni necesar.

Mediul de deployment al NexusOps include backend FastAPI, frontend React/Vite și bază de date PostgreSQL. Pentru dezvoltare și validare locală, PostgreSQL este pornit prin Docker Compose. Validarea documentată a proiectului include rularea testelor backend, verificarea build-ului frontend, linting-ul frontend și verificarea unui singur head Alembic. Pentru testarea interfeței și a fluxurilor operaționale, proiectul folosește și un mediu remote de dezvoltare/test, pe care sunt rulate manual scenariile critice înainte de realizarea capturilor finale pentru lucrare.

[Figura 5.1 – Mediul de testare NexusOps]

[Tabelul 5.1 – Resursele utilizate în procesul de testare]

| Resursă | Rol în testare | Observații |
| --- | --- | --- |
| Proxmox | Provider de virtualizare | Folosit pentru discovery, lifecycle control, VM/LXC provisioning |
| VM Ubuntu Server 24.04 | Host demonstrativ principal | Scenariu Docker demo host cu Inventory, Jobs, Identity și Deployments |
| LXC Proxmox | Validare container lifecycle și înregistrare | Suport implementat pentru discovery, provisioning de bază și Inventory registration |
| PostgreSQL | Persistență NexusOps | Folosit în dezvoltare locală prin Docker Compose și în deployment |
| Backend FastAPI | Control plane NexusOps | Validează, orchestrează și persistă operațiile |
| Frontend React/Vite | Interfață web | Folosit pentru operarea platformei și capturi de teză |
| Docker Engine | Runtime aplicații | Folosit pentru Portainer, cAdvisor și Nginx demonstrativ |
| Prometheus/Grafana/Loki | Observabilitate externă | Folosite ca provider-e de readiness și linkuri operaționale, nu ca sisteme înlocuite de NexusOps |
| Tailscale | Rețea privată opțională | Implementat ca integrare/pachet posibil, în afara fluxului principal de demo |
| Mediu remote development/test | Validare manuală | Folosit pentru confirmarea fluxurilor înainte de capturile finale |

---

# 5.8 Scenarii de utilizare

Scenariile de utilizare au fost selectate pentru a acoperi funcțiile reale implementate în NexusOps. Ele verifică atât operațiile de bază, cât și interacțiunea dintre domenii: Inventory, Proxmox, Jobs, Credential Manager, Deployments, Identity, Monitoring și Remote Access.

## 1. Infrastructure Discovery

Obiectivul acestui scenariu este verificarea capacității NexusOps de a descoperi resurse infrastructurale din Proxmox. Platforma trebuie să poată afișa noduri, mașini virtuale, containere LXC, storage și informații de sumar despre cluster.

Descrierea scenariului presupune configurarea unei integrări Proxmox și accesarea paginii Infrastructure. Backend-ul interoghează Proxmox, normalizează răspunsurile și trimite frontend-ului date despre hypervisor-e, VM-uri și containere.

Rezultatul așteptat este afișarea resurselor descoperite, fără ca acestea să fie automat transformate în ținte administrate. Operatorul trebuie să poată distinge între resurse unmanaged și resurse deja legate de Inventory.

Rezultatul actual este implementat: platforma oferă dashboard de infrastructură, descoperire Proxmox, carduri de noduri, tabele sau carduri pentru VM/LXC și status de sincronizare. Acest scenariu este o bază pentru Inventory Synchronization.

Screenshot recomandat: pagina Infrastructure cu noduri Proxmox, VM-uri și LXC-uri descoperite.

## 2. Inventory Synchronization

Obiectivul este validarea relației dintre resursele descoperite în Proxmox și modelul Inventory din NexusOps. Platforma trebuie să permită importul resurselor relevante și reconcilierea stării lor.

Descrierea scenariului presupune alegerea unei VM sau a unui container descoperit și importul său în Inventory cu metadate de execuție, cum ar fi IP, username SSH și eventual credential reference. Reconcilierea actualizează starea provider, sync status și metadatele asociate.

Rezultatul așteptat este apariția nodului ca entitate administrată în Inventory, fără distrugerea sau modificarea necontrolată a infrastructurii provider-side.

Rezultatul actual este implementat și folosit: importul în Inventory, reconcilierea Proxmox, clasificarea nodurilor ca VM, LXC sau hypervisor și lifecycle-ul managed/unmanaged/archived sunt prezente. Backlog-ul menționează că probleme precum importul din Infrastructure și conflictele de re-import au fost remediate.

Screenshot recomandat: resursă Proxmox unmanaged înainte de import și aceeași resursă vizibilă în Inventory după import.

## 3. Virtual Machine Provisioning

Obiectivul este crearea unei mașini virtuale prin Proxmox template și înregistrarea ei automată în Inventory. Scenariul demonstrează trecerea de la intenția operatorului la un host administrat.

Descrierea scenariului include alegerea unui template cloud-init, configurarea resurselor, rețelei, utilizatorului, adresei IP și, opțional, a bootstrap-ului prin profile sau package-uri. Platforma clonează template-ul, configurează VM-ul, pornește instanța, așteaptă disponibilitatea SSH și înregistrează nodul.

Rezultatul așteptat este existența unui VM în Proxmox, apariția sa în Inventory și posibilitatea rulării de Jobs sau bootstrap ulterior.

Rezultatul actual este implementat la nivel de funcționalitate și acoperit prin teste pentru ordinea Inventory registration -> bootstrap Jobs. Documentația menționează însă că full unattended VM provisioning plus profile/package/deployment application încă necesită o validare remote end-to-end curată înainte de a fi prezentat ca complet demonstrat în capturile finale.

Screenshot recomandat: formularul Provisioning completat, istoricul cererii și nodul rezultat în Inventory.

## 4. LXC Provisioning

Obiectivul este validarea suportului pentru containere LXC în aceeași paradigmă de managed nodes. Platforma trebuie să poată crea sau descoperi containere LXC și să le înregistreze în Inventory atunci când sunt administrabile.

Descrierea scenariului implică selectarea unui template LXC, configurarea CTID-ului, nodului, storage-ului și rețelei, urmată de crearea containerului și de înregistrarea acestuia în Inventory. Readiness-ul SSH este tratat separat de existența containerului în Proxmox.

Rezultatul așteptat este apariția containerului în Proxmox și, dacă sunt disponibile metadatele necesare, în Inventory ca nod LXC.

Rezultatul actual este implementat ca foundation: descoperire LXC, lifecycle start/stop/restart/shutdown, sincronizare, înregistrare și provisioning de bază. Limitările rămase includ validare mai profundă de rețea, descoperire mai bogată a storage-ului și filesystem editing avansat.

Screenshot recomandat: provisioning LXC și afișarea containerului în Infrastructure/Inventory.

## 5. Docker Deployment

Obiectivul este verificarea capacității platformei de a defini și executa un deployment Docker Compose pe un host din Inventory.

Descrierea scenariului include crearea unui deployment cu fișier Compose, selectarea hosturilor țintă, configurarea variabilelor de mediu, alegerea credentialelor pentru secrete și execuție, apoi rularea operației deploy. Pentru demo, serviciile recomandate sunt Portainer, cAdvisor și un Nginx demonstrativ.

Rezultatul așteptat este rularea containerelor pe host, persistența execuțiilor și afișarea stării runtime în dashboard-ul Deployments.

Rezultatul actual este implementat. Deployment-urile suportă create/edit, deploy, redeploy, restart, stop, status, logs, runtime refresh, multi-target state, credential-backed env și execuție prin Jobs. Manual, credential references, package execution și comportamentele de deployment au fost retestate în mediul remote, dar unele îmbunătățiri precum dry-run preview și runtime stale/failure diagnostics sunt încă marcate în backlog ca needing testing.

Screenshot recomandat: deployment card cu runtime state, target host, logs/inspect și servicii accesibile în browser.

## 6. Identity Discovery

Obiectivul este descoperirea utilizatorilor și grupurilor Linux existente pe hosturi administrate.

Descrierea scenariului presupune selectarea unuia sau mai multor hosturi și rularea acțiunilor de discovery pentru users/groups. Rezultatele sunt afișate în interfața Identity, cu context despre hostul de origine.

Rezultatul așteptat este ca operatorul să poată vedea utilizatorii și grupurile existente și să decidă dacă le adoptă ca înregistrări administrate.

Rezultatul actual este implementat. Backlog-ul menționează că problemele inițiale de Identity discovery și user creation au fost remediate, iar host-origin context pentru utilizatori și grupuri descoperite a fost adăugat. Noua interfață Identity este implementată, dar încă are elemente marcate pentru testare manuală mai largă.

Screenshot recomandat: Identity Explorer cu utilizatori/grupuri descoperite și host-origin chips.

## 7. User Management

Obiectivul este validarea administrării utilizatorilor platformei NexusOps și a utilizatorilor Linux orchestrați pe hosturi.

Pentru utilizatorii platformei, scenariul presupune autentificare, administrare prin Users & RBAC, roluri admin/operator/viewer, activare/dezactivare și resetare parolă. Pentru utilizatorii Linux, scenariul presupune definirea unui user, asocierea unei parole prin Credential Manager, alegerea credentialului de execuție/sudo și replicarea pe hosturi.

Rezultatul așteptat este separarea clară între identitatea platformei și identitatea Linux. Utilizatorul NexusOps controlează accesul la aplicație, iar Identity Management configurează conturi Linux pe infrastructură.

Rezultatul actual este implementat. Admin user lifecycle, RBAC, JWT sessions, token revocation și Identity Linux orchestration sunt prezente. Backlog-ul confirmă manual că separarea dintre account password credential și execution/sudo credential a fost corectată și testată.

Screenshot recomandat: Users & RBAC pentru utilizatorii platformei și formularul Identity pentru Linux user cu credentiale separate.

## 8. SSH Remote Access

Obiectivul este validarea accesului interactiv la hosturi administrate prin backend, fără expunerea credentialelor SSH către browser.

Descrierea scenariului include deschiderea Host Tools pentru un nod Inventory, obținerea unui token scoped pentru shell, deschiderea conexiunii WebSocket și folosirea browserului de fișiere/SFTP.

Rezultatul așteptat este accesul la shell și fișiere doar pentru admin/operator, cu refuz pentru viewer, cu target limitat la noduri Inventory-managed.

Rezultatul actual este implementat. Remote Access include shell WebSocket, scoped tokens, SFTP list/read/write, hash-checked writes, write allowlist pentru operatori și trust-on-first-use SSH fingerprint. Backlog-ul listează File Management / remote file access ca funcționalitate working.

Screenshot recomandat: Host Tools cu terminal conectat și browser de fișiere.

## 9. Monitoring Validation

Obiectivul este verificarea readiness-ului de monitorizare pentru nodurile administrate.

Descrierea scenariului presupune configurarea integrărilor Prometheus/Grafana/Loki unde sunt disponibile, rularea validării și consultarea paginii Monitoring. NexusOps verifică stări precum exporter availability, metrics/log readiness, stale telemetry și provider health.

Rezultatul așteptat este afișarea unei stări persistente pentru fiecare nod, fără ca pagina să depindă de interogări live costisitoare la fiecare randare.

Rezultatul actual este implementat ca monitoring readiness board cu snapshoturi persistente, validation attempts, state monitored/partial/unmonitored/stale/unknown, linkuri Grafana și validări ale componentelor locale. Limitările reale sunt că deep log exploration și indexing centralizat de loguri rămân viitor, iar primul demo simplificat nu include monitoring deep dive.

Screenshot recomandat: Monitoring overview cu provider health, node readiness și Grafana link.

## 10. Credential Management

Obiectivul este validarea gestionării securizate a secretelor reutilizabile.

Descrierea scenariului include crearea unui credential, folosirea lui în Inventory, Jobs, Deployments sau Identity, ștergerea în Trash, restaurarea și blocarea purge-ului atunci când există referințe active.

Rezultatul așteptat este ca secretul să fie stocat criptat, să nu fie afișat de frontend și să fie rezolvat doar server-side în execuții.

Rezultatul actual este implementat și parțial validat manual. Credential Manager, masked API responses, references, Trash lifecycle și blocarea purge-ului pentru referințe active sunt prezente. Manual retesting din 2026-06-18 confirmă credential references și Trash behavior în mediul remote, cu observația că interfața Trash încă are o dublare de navigație între Credentials Trash și general Trash.

Screenshot recomandat: Credential Manager cu listă mascată și pagina Trash cu referințe active.

---

# 5.9 Fluxuri operaționale

Fluxurile operaționale demonstrează modul în care funcțiile NexusOps se combină pentru a susține activități reale de administrare. În loc ca utilizatorul să lucreze cu instrumente izolate, platforma urmărește o succesiune coerentă: selectarea unei ținte, validarea stării, execuția prin backend și verificarea rezultatului.

## Provisioning Flow

Declanșatorul acestui flux este cererea operatorului de a crea o VM sau un container LXC. Operatorul completează formularul de Provisioning sau alege un blueprint, apoi furnizează valorile unice pentru mașină.

Pașii principali sunt: selectarea template-ului, configurarea resurselor, configurarea rețelei, lansarea clone/create în Proxmox, polling-ul task-ului Proxmox, verificarea SSH, înregistrarea în Inventory și rularea bootstrap-ului opțional. Componentele implicate sunt frontend-ul Provisioning, backend-ul Provisioning, adaptorul Proxmox, Inventory, Jobs, Packages și Profiles.

Rezultatul este un nod nou în Inventory, pregătit pentru operații ulterioare. Pentru teza finală, acest flux trebuie capturat printr-un run remote complet, deoarece documentația curentă menționează că validarea full unattended plus profile/package/deployment încă trebuie finalizată end-to-end.

[Figura 5.2 – Fluxul de provisionare]

```text
Operator -> Provisioning UI -> Proxmox template/cloud-init
        -> VM/LXC created -> SSH readiness
        -> Inventory registration -> Bootstrap Jobs
        -> Managed host
```

## Deployment Flow

Declanșatorul este cererea operatorului de a lansa sau actualiza un deployment Docker Compose. Operatorul creează sau editează un deployment, selectează hosturile țintă și configurează secretele prin Credential Manager.

Pașii sunt: validarea Compose, dry-run preview unde este folosit, rezolvarea credentialelor, crearea execuției de deployment, crearea execuțiilor per target, rularea comenzilor Docker Compose prin Jobs și SSH, persistarea outputului și refresh-ul runtime state.

Componentele implicate sunt Deployments UI, Deployments backend service, Credential Manager, Jobs, SSH adapter, Inventory și hostul Docker. Rezultatul este o aplicație containerizată pornită, o stare runtime vizibilă și istoric de execuție.

[Figura 5.3 – Fluxul de deployment]

```text
Deployment definition -> Inventory target(s)
        -> credential refs -> Job per target
        -> Docker Compose command
        -> runtime refresh -> deployment dashboard
```

## Identity Management Flow

Declanșatorul este cererea de a descoperi, crea, adopta sau replica utilizatori și grupuri Linux. Operatorul lucrează din pagina Identity și selectează hosturile țintă din Inventory.

Pașii includ definirea stării dorite, selectarea credentialelor pentru parola contului și/sau pentru execuție sudo, generarea operațiilor Linux, rularea fanout-ului prin Jobs și afișarea rezultatului per host. Componentele implicate sunt Identity UI, Identity backend, Credential Manager, Jobs, SSH adapter și hosturile Linux.

Rezultatul este aplicarea controlată a utilizatorilor, grupurilor, cheilor SSH sau permisiunilor pe hosturi. Backlog-ul confirmă că problemele critice legate de sudo și separarea credentialelor au fost remediate, însă noua interfață Identity necesită încă testare manuală amplă.

[Figura 5.4 – Fluxul de administrare a identităților]

```text
Identity desired state -> target hosts
        -> account credential / execution credential
        -> Jobs fanout -> SSH commands
        -> per-host identity result
```

## Monitoring Validation Flow

Declanșatorul este refresh-ul manual sau programat al stării de monitoring/runtime. Platforma nu rulează interogări live grele în timpul fiecărei randări a paginii.

Pașii includ citirea nodurilor Inventory-managed, verificări TCP/HTTP/SSH unde sunt configurate, validarea componentelor precum node_exporter, promtail și cAdvisor, actualizarea snapshoturilor și afișarea stării în frontend. Componentele implicate sunt Monitoring UI, Monitoring backend, Runtime State, Inventory, Integrations și providerii Prometheus/Grafana/Loki.

Rezultatul este o stare de readiness persistentă, care poate fi consultată fără a bloca interfața sau a crea dependențe continue de providerii externi.

[Figura 5.5 – Fluxul de validare monitoring]

```text
Refresh trigger -> backend validation
        -> provider/local checks
        -> monitoring snapshot
        -> frontend readiness board
```

## Remote Access Flow

Declanșatorul este deschiderea Host Tools pentru un nod administrat. Utilizatorul trebuie să aibă rol operator sau admin.

Pașii sunt: frontend-ul cere un token scoped pentru shell, backend-ul validează utilizatorul și serverul, frontend-ul deschide conexiunea WebSocket cu tokenul primit, backend-ul creează canal SSH și transmite datele terminalului. Pentru fișiere, frontend-ul folosește API-uri SFTP prin backend.

Componentele implicate sunt Host Tools UI, Remote Access backend, Credential Manager, Inventory, SSH adapter și hostul țintă. Rezultatul este acces interactiv controlat, fără expunerea credentialelor către browser.

[Figura 5.6 – Fluxul de acces remote]

```text
Host Tools -> scoped shell token
        -> WebSocket
        -> backend SSH channel
        -> managed host
```

---

# 5.10 Rezultate obținute

Rezultatele obținute demonstrează că NexusOps a evoluat dincolo de un prototip simplu de inventar și oferă un MVP funcțional pentru administrarea infrastructurii Linux într-un mediu Proxmox. Platforma implementează autentificare locală, RBAC, Inventory, Proxmox discovery, VM/LXC provisioning, Jobs, package execution, profiles, deployments, identity orchestration, monitoring readiness, Credential Manager, Remote Access, Workflows și Automations.

Funcționalitățile validate automat includ testele backend, build-ul frontend, linting-ul frontend și verificarea Alembic. În ultima verificare de documentație și readiness, comenzile de validare au trecut cu frontend lint, frontend build, 175 teste backend și un singur head Alembic. Acest rezultat confirmă stabilitatea de bază a codului și faptul că schimbările documentate nu au introdus regresii evidente.

Funcționalitățile validate manual includ mai multe fluxuri operaționale: Identity sudo-backed synchronization, Deployment edit save and target change, Deployment execution credential, Package execution credential selector, search across operational pages, credential references, universal Trash lifecycle și Provisioning bootstrap profile/package selection UX. Backlog-ul marchează aceste elemente ca Fixed/Tested sau confirmate în mediul remote.

În timpul testării au fost descoperite probleme reale. Exemplele includ eșecuri la sincronizarea Identity în moduri sudo, confuzia dintre credentialul de parolă cont și credentialul de execuție/sudo, probleme la editarea deployment-urilor cu istoric, importuri Inventory blocate de înregistrări stale, credential deletion care putea rupe Inventory reads și neclarități în diagnosticarea runtime a deployment-urilor.

Fixurile aplicate au îmbunătățit platforma semnificativ. Sudo handling a fost standardizat printr-un mecanism comun, Identity separă account password de execution credential, Deployment păstrează corect țintele și execution credentials, Credential Manager folosește Trash și blochează purge-ul când există referințe active, iar deployment-urile au primit diagnostics, runtime age, failure reasons și dry-run preview.

Statusul operațional final este unul de MVP larg funcțional, dar cu limite explicite. Funcțiile principale sunt implementate, multe au fost validate automat și manual, iar fluxul demonstrativ pentru teză este definit. Totuși, documentația curentă recomandă încă un run remote end-to-end curat pentru capturile finale ale fluxului complet: provisioning, profile steps, deployment runtime, validation jobs și accesibilitatea Portainer/cAdvisor/Nginx.

[Tabelul 5.2 – Rezultatele testelor efectuate]

| Zonă validată | Tip validare | Rezultat actual |
| --- | --- | --- |
| Frontend lint | Automat | Trecut |
| Frontend build | Automat | Trecut |
| Backend tests | Automat | 175 teste trecute la ultimul review de readiness |
| Alembic heads | Automat | Single head validat |
| Identity sudo-backed sync | Manual | Fixed/Tested |
| Deployment target edit/save | Manual + regresie backend | Fixed/Tested |
| Deployment execution credential | Manual | Fixed/Tested |
| Package execution credential | Manual | Fixed/Tested |
| Credential references | Manual remote retest | Confirmat |
| Universal Trash lifecycle | Manual remote retest | Confirmat, cu cleanup UI rămas |
| Full unattended VM + profile/package/deployment | End-to-end remote | Încă necesită validare finală curată |

---

# 5.11 Limitări identificate

Limitările identificate reflectă stadiul actual al platformei și sunt importante pentru a delimita corect contribuția proiectului. NexusOps este un MVP funcțional pentru orchestrare homelab/lab, nu o platformă enterprise completă.

La nivel de platformă, nu sunt implementate SSO, MFA, API keys și permisiuni fine-grained. Autentificarea locală, JWT sessions și RBAC admin/operator/viewer sunt implementate, dar integrarea cu provideri externi precum Google SSO, OIDC, SAML, LDAP sau Active Directory este în afara implementării curente.

La nivel de execuție, Jobs rulează local/in-process, iar distributed background workers nu sunt implementați. Automations folosesc scheduler și coadă async în proces, potrivite pentru MVP, dar nu echivalente cu un sistem distribuit cu leases, retries și idempotency keys.

La nivel de provisioning, fluxul template/cloud-init este implementat, dar workflow chaining complet și orchestration-ul fiecărei faze ca WorkflowRun deplin rămân viitor. Full unattended provisioning plus profile/package/deployment bootstrap este funcțional ca model, dar necesită încă validare remote end-to-end curată înainte de capturile finale.

La nivel Proxmox, lifecycle actions sunt intenționat limitate la acțiuni controlate precum start, stop, reboot și shutdown. Provider-side VM deletion pentru QEMU nu este implementat ca flux general. De asemenea, task history și polling complet pentru toate acțiunile provider rămân direcții de îmbunătățire.

La nivel monitoring, NexusOps oferă readiness și snapshoturi persistente, dar nu înlocuiește Prometheus, Loki sau Grafana. Nu există deep log exploration, indexare centralizată de loguri sau generare automată de dashboard-uri Grafana.

La nivel Identity Management, platforma orchestrează identitate Linux, dar nu este un sistem centralizat de autentificare. Nu implementează LDAP, Kerberos, FreeIPA, Active Directory, SSSD sau PAM federation. De asemenea, per-host identity drift matrix și snapshoturi persistente detaliate pentru fiecare host rămân viitor.

La nivel Docker Deployments, NexusOps poate gestiona deployment-uri create sau definite explicit, dar nu implementează încă discovery/adoption pentru proiecte Compose existente și nici removal destructiv complet de pe mașină. Ștergerea unei înregistrări NexusOps rămâne separată de oprirea și ștergerea serviciilor de pe host.

La nivel frontend, nu există încă frontend automated test coverage. Verificarea frontend se bazează pe lint, build și testare manuală. De asemenea, sincronizarea runtime se bazează pe polling/read-refresh, nu pe un sistem real-time complet.

---

# 5.12 Direcții de îmbunătățire

O primă direcție realistă de îmbunătățire este extinderea RBAC-ului. Modelul actual admin/operator/viewer este potrivit pentru MVP, dar o platformă matură ar beneficia de permisiuni mai granulare: cine poate rula Jobs, cine poate gestiona credentiale, cine poate executa deployment-uri sau cine poate accesa Remote Access.

Integrarea cu provideri externi de identitate este o direcție importantă. OIDC, SAML, LDAP sau Active Directory ar permite integrarea NexusOps într-un mediu organizațional existent, reducând administrarea separată a utilizatorilor platformei. Această direcție trebuie tratată separat de Identity Management-ul Linux, care are alt scop.

Integrarea Terraform ar extinde platforma din zona de orchestrare operațională în zona de infrastructure as code. Beneficiul ar fi administrarea declarativă a resurselor, plan/apply și control mai riguros al schimbărilor. Totuși, integrarea trebuie făcută fără a rupe modelul Inventory-centric.

Integrarea Ansible ar adăuga un mecanism matur pentru configurarea hosturilor. NexusOps ar putea păstra rolul de control plane și audit, iar Ansible ar executa playbook-uri standardizate. Beneficiul ar fi reutilizarea ecosistemului Ansible pentru configurări complexe.

Suportul Kubernetes ar extinde platforma către workload-uri containerizate orchestrate la scară mai mare. În prezent NexusOps gestionează Docker Compose pe hosturi administrate. Kubernetes ar introduce noi concepte precum clusters, namespaces, workloads, secrets și policies.

Monitoring-ul extins ar putea include log exploration, integrare mai profundă cu Loki, vizualizări istorice, alerting și corelarea evenimentelor runtime cu Jobs și Deployments. Beneficiul ar fi o experiență operațională mai completă, fără a transforma NexusOps într-un înlocuitor direct pentru Grafana.

Policy enforcement și command approval ar îmbunătăți siguranța operațiilor. Platforma are deja fundații pentru command policy și detectarea unor comenzi riscante, dar un workflow complet de aprobare ar permite control mai bun în echipe.

Multi-hypervisor support ar permite folosirea platformei și în afara Proxmox. Un model de adaptoare pentru VMware, Hyper-V, libvirt sau cloud providers ar extinde aria de aplicabilitate. Beneficiul ar fi transformarea NexusOps într-un control plane mai general, păstrând Inventory ca model comun.

O direcție tehnică importantă este mutarea operațiilor lungi către workers distribuiți, cu idempotency keys, execution leases și retry policies. Aceasta ar crește fiabilitatea pentru provisioning, deployments și operații bulk.

În zona frontend, introducerea testelor automate și a unui model mai fin de sincronizare runtime ar îmbunătăți stabilitatea experienței de utilizare. Teste pentru login, Inventory target selection, Jobs, Deployments și Remote Access ar reduce riscul de regresii în fluxurile critice.

---

# Recommended Screenshots

| Screenshot title | De ce este util | Secțiune |
| --- | --- | --- |
| Login și roluri utilizator | Demonstrează autentificarea și accesul controlat | 5.7, 5.8 |
| Infrastructure dashboard Proxmox | Arată descoperirea nodurilor, VM-urilor și LXC-urilor | 5.8 Infrastructure Discovery |
| Import Proxmox VM/LXC în Inventory | Demonstrează trecerea de la discovery la managed target | 5.8 Inventory Synchronization |
| Inventory dashboard cu runtime badges | Arată Inventory ca sursă de adevăr operațional | 5.8, 5.9 |
| Provisioning form cu blueprint | Arată configurarea VM/LXC înainte de creare | 5.8 Virtual Machine Provisioning |
| Provisioning history completat | Demonstrează rezultatul și lifecycle-ul cererii | 5.8 Virtual Machine Provisioning |
| Host Detail pentru VM provisionat | Arată nodul administrat după înregistrare | 5.8, 5.9 Provisioning Flow |
| Jobs page cu output de validare | Oferă dovadă de execuție și audit | 5.8, 5.10 |
| Packages/Profile execution modal | Demonstrează variabile și credential references | 5.8, 5.9 |
| Deployment create/edit drawer | Arată definirea Docker Compose și target selection | 5.8 Docker Deployment |
| Deployment card cu runtime state | Demonstrează starea aplicației după deploy | 5.8, 5.10 |
| Portainer accesibil în browser | Dovadă vizuală că deployment-ul a produs un serviciu real | 5.8 Docker Deployment |
| cAdvisor accesibil în browser | Dovadă pentru runtime monitoring al containerelor | 5.8 Docker Deployment |
| Demo Nginx page | Rezultat simplu și clar al orchestration-ului | 5.8 Docker Deployment |
| Identity Explorer cu host-origin | Arată discovery și contextul utilizatorilor/grupurilor | 5.8 Identity Discovery |
| Identity replicate modal/results | Demonstrează aplicarea user/group/key/permission pe hosturi | 5.8 User Management |
| Users & RBAC page | Arată administrarea utilizatorilor platformei | 5.8 User Management |
| Credential Manager masked list | Demonstrează protecția secretelor | 5.8 Credential Management |
| Universal Trash cu referințe pentru credentials | Arată lifecycle restore/purge și blocarea purge-ului | 5.8 Credential Management |
| Host Tools terminal | Demonstrează Remote Access prin token scoped și WebSocket | 5.8 SSH Remote Access |
| Host Tools file browser | Arată SFTP list/read/write prin backend | 5.8 SSH Remote Access |
| Monitoring overview | Arată readiness, stale/degraded states și provider health | 5.8 Monitoring Validation |
| Workflows timeline | Arată vizibilitatea proceselor multi-pas | 5.9 Fluxuri operaționale |
| Automations page | Arată scheduling și runtime state pentru operații recurente | 5.9 Fluxuri operaționale |
