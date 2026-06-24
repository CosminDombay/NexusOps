# 4.4 Proiectarea bazei de date

Acest document descrie proiectarea bazei de date NexusOps din perspectiva arhitecturii sistemului. Scopul sau este sa sustina redactarea capitolului de licenta, nu sa inlocuiasca schema SQL, migratiile sau documentatia de implementare.

## 1. General Database Design

Baza de date NexusOps exista pentru a pastra starea persistenta a platformei de orchestrare: inventarul infrastructurii, utilizatorii platformei, istoricul executiilor, definitiile operationale, credentialele, automatizarile, deployment-urile si starile runtime observate.

Fara aceasta baza de date, aplicatia ar fi doar un strat temporar de apeluri catre Proxmox, SSH sau servicii de monitorizare. Prin persistenta, NexusOps poate urmari ce infrastructura administreaza, ce operatii au fost cerute, cine le-a initiat, ce rezultat au avut si ce stare operationala are fiecare nod.

PostgreSQL a fost ales deoarece platforma are un model relational clar. Serverele din Inventory sunt referentiate de Jobs, Deployments, Monitoring, Identity, Provisioning si Remote Access. Utilizatorii sunt legati de sesiuni, tokenuri si audit. Credentialele sunt referentiate de mai multe domenii. PostgreSQL ofera integritate relationala, tranzactii, indecsi, tipuri structurate si suport solid pentru campuri JSON, utile pentru metadate operationale, rezultate runtime si configuratii flexibile.

In arhitectura platformei, baza de date sustine modular monolith-ul NexusOps ca strat comun de adevar. Modulele backend nu comunica prin stari volatile, ci prin entitati persistente: Inventory defineste tintele, Jobs pastreaza executiile, Credentials gestioneaza materialele sensibile, iar domeniile de provisioning, deployment, identity si monitoring construiesc peste aceste fundatii.

## 2. Main Business Domains

### Inventory Management

Scopul domeniului Inventory Management este sa ofere catalogul central al infrastructurii administrate. Entitatea principala este nodul administrat, reprezentat conceptual ca Server sau Inventory Node.

Acest domeniu stocheaza informatii precum hostname, adresa IP, tipul nodului, mediul, providerul, identificatorul extern, starea de management, starea de sincronizare, capabilitatile, metadatele Proxmox si informatiile necesare pentru conectare SSH.

Inventory este centrul sistemului. Jobs, Deployments, Provisioning, Monitoring, Runtime, Identity si Remote Access depind conceptual de Inventory. Orice operatie pe infrastructura trebuie sa porneasca de la un nod cunoscut si administrat de platforma.

### Provisioning

Provisioning descrie si urmareste crearea de masini virtuale sau containere prin Proxmox si inregistrarea rezultatului in Inventory.

Entitatile principale sunt Provisioning Request, Virtual Machine, Provisioning Blueprint, Provisioning Batch si Bootstrap Template. Domeniul pastreaza informatii despre template-ul Proxmox, nodul tinta, resurse CPU, memorie, disc, configuratie de retea, cloud-init, statusul procesului, task-urile Proxmox si pasii de bootstrap.

Relatia principala este cu Inventory: dupa creare, provisioning-ul produce sau leaga un Server din Inventory. Bootstrap-ul poate folosi Profiles, Packages si Jobs pentru configurarea initiala a hostului.

### Deployments

Deployments gestioneaza aplicatii Docker Compose rulate pe hosturi administrate.

Entitatile principale sunt Deployment, Deployment Target, Deployment Execution, Deployment Target Execution si Deployment Revision. Acestea pastreaza definitia Compose, continutul de mediu, referintele la credentiale, hosturile tinta, path-ul remote, starea deployment-ului, istoricul executiilor, outputul si starea runtime a containerelor.

Deployment Target depinde de Inventory deoarece fiecare tinta trebuie sa fie un host administrat. Executiile depind de Jobs, iar secretele aplicatiei si credentialele de executie depind de Credential Management.

### Identity Management

Identity Management se ocupa de orchestrarea identitatii Linux pe hosturile administrate. Nu reprezinta un sistem centralizat de autentificare de tip LDAP, Active Directory sau SSO.

Entitatile principale sunt Linux User, Linux Group, SSH Key, Permission Template si Identity Execution. Domeniul stocheaza utilizatori Linux, shell, home directory, stare locked, grupuri, membri, chei SSH, template-uri de permisiuni si istoricul aplicarii pe hosturi.

Identity defineste starea dorita, iar aplicarea efectiva pe infrastructura se face prin Inventory si Jobs. Parolele de cont pot referi Credential Manager, separat de credentialul folosit pentru executie sau sudo.

### Credential Management

Credential Management gestioneaza secrete operationale reutilizabile.

Entitatile principale sunt Credential, Credential Usage si Variable. Domeniul stocheaza tipul credentialului, username, secret criptat, chei SSH, API tokens, env secrets, scope, tag-uri si lifecycle de stergere sau restaurare.

Credentialele sunt folosite prin referinte, nu prin copierea valorilor secrete in alte domenii. Inventory poate referi credentiale SSH; Deployments, Automations, Integrations, Packages, Profiles, Variables si Identity pot referi credentiale fara a stoca valori plaintext.

### Automation & Workflows

Automation si Workflows modeleaza planificarea, declansarea si urmarirea operatiilor compuse.

Entitatile principale sunt Automation, Workflow Run, Workflow Step si Job. Domeniul pastreaza reguli cron sau interval, tipul operatiei, hosturile tinta, variabile, credential refs, starea workflow-ului, pasii, logurile si rezultatele.

Automation poate declansa Jobs, Packages, Profiles sau Deployments. Workflow structureaza executii mai mari, iar Jobs raman unitatea atomica de executie pe host.

### Monitoring & Runtime

Monitoring si Runtime pastreaza o imagine persistenta despre starea operationala a nodurilor si deployment-urilor.

Entitatile principale sunt Monitoring Snapshot, Monitoring Validation Attempt, Metric Sample, Node Runtime Snapshot, Runtime Refresh Event si Runtime Refresh Status. Acestea pastreaza readiness monitoring, statusul exporterelor, starea targeturilor Prometheus, staleness, metrici runtime, motive de degradare si statusul refresh-urilor.

Acest domeniu este legat direct de Inventory si, unde este cazul, de Integration records si Audit Events. Starea runtime este citita din baza de date pentru a evita interogari live costisitoare la fiecare randare de pagina.

### Platform Security & Access Control

Platform Security & Access Control controleaza cine foloseste NexusOps si ce operatii poate executa.

Entitatile principale sunt User, Refresh Token Session, Remote Access Token si Audit Event. Domeniul pastreaza utilizatori locali, roluri admin/operator/viewer, sesiuni, tokenuri scoped pentru remote access si evenimente de audit.

Jobs si Audit pot referi User, iar Remote Access Token leaga un User de un Server pentru operatii limitate si temporare.

## 3. Core Business Entities

| Entity | Purpose | Main relationships | Why it exists |
| --- | --- | --- | --- |
| Server / Inventory Node | Reprezinta o masina administrabila | Credentials, Jobs, Provisioning, Deployments, Monitoring, Identity | Este sursa de adevar pentru tintele operationale |
| Credential | Reprezinta un secret reutilizabil | Inventory, Deployments, Integrations, Variables, Identity, Automations | Separa datele sensibile de definitiile operationale |
| Job | Executie atomica pe un host | Server, User, Deployment, Identity, Package/Profile flows | Ofera istoric, audit si rezultate pentru operatiile SSH |
| Provisioning Request | Cerere de creare VM sau LXC | Blueprint, Batch, Server, bootstrap Jobs | Leaga intentia de creare de rezultatul infrastructurii |
| Deployment | Definitie Docker Compose administrata | Targets, Executions, Credentials, Jobs | Modeleaza aplicatiile rulate pe hosturi |
| Deployment Target | Instanta a unui deployment pe un server | Deployment, Server, Job | Permite deployment multi-host si stare per host |
| Linux User / Group | Stare dorita pentru identitate Linux | Credentials, Identity Execution, Jobs | Permite replicarea controlata a identitatii pe hosturi |
| Workflow Run | Proces operational compus | Steps, Server, Audit | Explica executiile multi-pas, nu doar comenzile individuale |
| Automation | Regula de executie programata | Inventory targets, Credentials, Jobs/Profiles/Deployments | Automatizeaza operatiile recurente |
| Monitoring Snapshot | Stare observata per nod | Server, Integration | Evita interogari live costisitoare in paginile normale |
| User | Utilizator al platformei NexusOps | Sessions, Jobs, Audit, Remote Access | Asigura autentificare, roluri si responsabilitate |
| Audit Event | Urma de audit | User, Workflow, target conceptual | Asigura trasabilitate pentru actiuni importante |

## 4. Entity Relationships

Entitatile care depind de Inventory sunt Jobs, Deployment Targets, Provisioning Requests, Virtual Machines, Monitoring Snapshots, Runtime Snapshots, Identity Executions, Remote Access Tokens, Package Installations si Command Executions. Conceptual, orice operatie pe infrastructura trebuie sa porneasca de la un nod din Inventory, nu de la un IP arbitrar.

Entitatile care depind de Credentials sunt Inventory pentru SSH, Deployments pentru env secrets si executie/sudo, Integrations pentru provider tokens, Variables pentru valori secrete, Identity pentru parole de cont, Automations, Profiles si Packages pentru variabile sau executii sensibile. Relatia este intentionat prin referinte, astfel incat secretul sa fie rezolvat server-side.

Entitatile care depind de Jobs sunt Deployments, Packages, Profiles, Identity si Automations. Jobs reprezinta stratul atomic de executie si pastreaza comanda redacted, outputul, statusul, durata si contextul operational.

Entitatile care depind de Users/Roles sunt Sessions, Remote Access Tokens, Jobs initiate manual, Audit Events si operatiile administrative. Rolurile controleaza accesul: viewer pentru citire, operator pentru executii operationale, admin pentru credentiale, utilizatori, integrari si audit.

## 5. ERD Recommendations

Pentru ERD-ul principal ar trebui incluse doar entitatile mari:

- User
- Server
- Credential
- Job
- ProvisioningRequest
- Deployment
- DeploymentTarget
- WorkflowRun
- Automation
- LinuxUser
- LinuxGroup
- MonitoringSnapshot
- Integration
- AuditEvent

Pentru a pastra diagrama lizibila, ERD-ul principal ar trebui sa excluda tabelele de suport sau de volum, precum sesiuni refresh, remote access tokens, job execution events, metric samples, runtime refresh status, deployment target execution, deployment revisions si credential usages. Acestea pot aparea in diagrame secundare.

Diagramele pe domenii recomandate sunt:

- Inventory-centric ERD: Server, Credential, Integration, Runtime Snapshot, Monitoring Snapshot.
- Execution ERD: Job, User, Audit Event, Workflow Run, Workflow Step.
- Deployment ERD: Deployment, Deployment Target, Deployment Execution, Target Execution, Job, Credential.
- Provisioning ERD: Blueprint, Batch, Provisioning Request, Virtual Machine, Server.
- Identity ERD: Linux User, Linux Group, SSH Key, Permission Template, Identity Execution, Job, Credential.
- Security ERD: User, Session, Remote Access Token, Audit Event, Server.

## 6. Architectural Principles

NexusOps foloseste un model de source of truth impartit pe domenii. Inventory este sursa de adevar pentru noduri, Credentials pentru secrete, Jobs pentru executii, Users pentru accesul in platforma, Deployments pentru definitii Compose, iar Identity pentru starea dorita a conturilor Linux.

Arhitectura este inventory-centric: toate operatiile importante se raporteaza la servere administrate. Aceasta decizie previne executii ad-hoc pe hosturi necunoscute si face posibila corelarea provisioning-ului, deployment-ului, monitorizarii si auditului.

Auditabilitatea este sustinuta prin Jobs, Workflow Runs, Deployment Executions si Audit Events. Sistemul poate raspunde la intrebari precum: cine a initiat operatia, pe ce host, cu ce rezultat si cand.

Consistenta datelor este obtinuta prin relatii clare intre domenii si prin stari lifecycle explicite: pending/running/success/failed, managed/unmanaged/retired, draft/running/degraded. Campurile JSON sunt folosite pentru metadate flexibile, dar entitatile centrale si relatiile critice raman relationale.

Separarea responsabilitatilor apare si in modelul de date. Inventory nu stocheaza istoric de executie, Jobs nu definesc infrastructura, Credentials nu apartin unui singur modul, iar Monitoring pastreaza snapshoturi citibile fara sa devina sistemul principal de observabilitate.

## 7. Chapter Support Material

| Material | Continut recomandat |
| --- | --- |
| ERD principal | User, Server, Credential, Job, Deployment, ProvisioningRequest, WorkflowRun, Automation, MonitoringSnapshot, AuditEvent |
| Diagrama Inventory-centric | Cum toate domeniile operationale depind de Server/Inventory |
| Diagrama Execution Pipeline | Profile/Package/Deployment/Identity/Automation -> Job -> Inventory Server |
| Diagrama Credentials | Credential ca referinta comuna pentru Inventory, Deployments, Integrations, Variables, Identity |
| Diagrama Monitoring Runtime | Server -> Runtime Snapshot / Monitoring Snapshot / Validation Attempt |
| Tabel domenii business | Domeniu, scop, entitati, relatii |
| Tabel entitati principale | Entitate, rol, relatii, justificare |
| Tabel principii arhitecturale | Source of truth, inventory-centric, auditability, consistency, separation of concerns |
