"""
KOLO - Scheduler v2.0
Robot de relances automatiques
Lancement : python scheduler.py
"""

import schedule
import time
import os
import json
import pandas as pd
import smtplib
import ssl
from datetime import date
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import anthropic

HEURE_ENVOI    = "08:00"
CONFIG_FILE    = "KOLO_config.json"
HISTORIQUE     = "historique_relances.xlsx"

REGLES_RELANCE = {
    "petit":     {"n1": 10, "n2": 25, "n3": None},
    "normal":    {"n1": 5,  "n2": 15, "n3": 30},
    "important": {"n1": 3,  "n2": 10, "n3": 20},
}

def get_categorie(montant: float) -> str:
    if montant < 1000:   return "petit"
    elif montant < 5000: return "normal"
    else:                return "important"

def get_delais(montant: float) -> dict:
    return REGLES_RELANCE[get_categorie(montant)]

def compter_relances_client(client: str) -> int:
    if not os.path.exists(HISTORIQUE):
        return 0
    df_hist = pd.read_excel(HISTORIQUE)
    if df_hist.empty:
        return 0
    mask = (
        (df_hist["Client"].astype(str) == str(client)) &
        (df_hist["Statut Envoi"] == "Envoye")
    )
    return int(mask.sum())

def charger_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}

def sauvegarder_config(config: dict):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

def scanner_dossier(dossier: str) -> pd.DataFrame:
    tous_les_df = []
    if not os.path.exists(dossier):
        print(f"[ERREUR] Dossier introuvable : {dossier}")
        return pd.DataFrame()
    for fichier in os.listdir(dossier):
        chemin = os.path.join(dossier, fichier)
        try:
            if fichier.endswith(".xlsx") or fichier.endswith(".xls"):
                df = pd.read_excel(chemin)
                df["_source"] = fichier
                tous_les_df.append(df)
            elif fichier.endswith(".csv"):
                df = pd.read_csv(chemin, sep=None, engine="python")
                df["_source"] = fichier
                tous_les_df.append(df)
        except Exception as e:
            print(f"[ERREUR] Impossible de lire {fichier} : {e}")
    if not tous_les_df:
        print(f"[INFO] Aucun fichier Excel/CSV trouve dans {dossier}")
        return pd.DataFrame()
    return pd.concat(tous_les_df, ignore_index=True)

def normaliser_colonnes(df: pd.DataFrame) -> pd.DataFrame:
    col_map = {}
    used_targets = set()
    for col in df.columns:
        c = col.lower().replace(" ", "").replace("_", "")
        target = None
        if any(x in c for x in ["echeance", "duedate"]):
            target = "Date Echeance"
        elif any(x in c for x in ["emission", "invoicedate"]):
            target = "Date Emission"
        elif any(x in c for x in ["statut", "status"]):
            target = "Statut"
        elif any(x in c for x in ["montant", "amount", "euros"]):
            target = "Montant"
        elif "email" in c or "mail" in c:
            target = "Email Client"
        elif any(x in c for x in ["client", "customer"]):
            target = "Client"
        elif any(x in c for x in ["facture", "numero", "invoice"]):
            target = "Numero Facture"
        if target and target not in used_targets:
            col_map[col] = target
            used_targets.add(target)
    df = df.rename(columns=col_map)
    df = df.loc[:, ~df.columns.duplicated()]
    for dc in ["Date Echeance", "Date Emission"]:
        if dc in df.columns:
            df[dc] = pd.to_datetime(df[dc], dayfirst=False, errors="coerce")
    today_ts = pd.Timestamp(date.today())
    if "Date Echeance" in df.columns:
        df["Jours Retard"] = (today_ts - df["Date Echeance"]).dt.days
        df["Jours Retard"] = df["Jours Retard"].apply(
            lambda x: max(0, int(x)) if pd.notna(x) else 0
        )
    return df

def determiner_niveau(jours: int, montant: float, client: str) -> int:
    delais      = get_delais(montant)
    nb_relances = compter_relances_client(client)
    bonus = 0
    if nb_relances >= 2: bonus = 5
    elif nb_relances == 1: bonus = 2
    n1 = max(1, delais["n1"] - bonus)
    n2 = max(1, delais["n2"] - bonus)
    n3 = delais["n3"]
    if n3 is not None and jours >= n3:
        return 3
    elif jours >= n2:
        return 2
    elif jours >= n1:
        return 1
    else:
        return 0

def deja_relance(numero_facture: str, niveau: int) -> bool:
    if not os.path.exists(HISTORIQUE):
        return False
    df_hist = pd.read_excel(HISTORIQUE)
    if df_hist.empty:
        return False
    mask = (
        (df_hist["Numero Facture"].astype(str) == str(numero_facture)) &
        (df_hist["Niveau"].astype(str) == f"Niveau {niveau}") &
        (df_hist["Statut Envoi"] == "Envoye")
    )
    return mask.any()

def ajouter_historique(row: pd.Series, niveau: int, statut: str):
    if os.path.exists(HISTORIQUE):
        df_hist = pd.read_excel(HISTORIQUE)
    else:
        df_hist = pd.DataFrame(columns=[
            "Date Envoi", "Numero Facture", "Client",
            "Montant", "Jours Retard", "Niveau",
            "Email Client", "Statut Envoi"
        ])
    nouvelle_ligne = {
        "Date Envoi":     date.today().strftime("%d/%m/%Y"),
        "Numero Facture": row.get("Numero Facture", "N/A"),
        "Client":         row.get("Client", "N/A"),
        "Montant":        row.get("Montant", 0),
        "Jours Retard":   row.get("Jours Retard", 0),
        "Niveau":         f"Niveau {niveau}",
        "Email Client":   row.get("Email Client", "N/A"),
        "Statut Envoi":   statut,
    }
    df_hist = pd.concat([df_hist, pd.DataFrame([nouvelle_ligne])], ignore_index=True)
    df_hist.to_excel(HISTORIQUE, index=False)

def generer_email(row: pd.Series, niveau: int) -> str:
    tone = {
        1: "tres courtois et chaleureux, suggere poliment qu'il s'agit d'un oubli.",
        2: "professionnel et serieux, deuxieme rappel, rappelle les consequences sans agressivite.",
        3: "juridique et strict, mise en demeure formelle, mentionne les penalites legales art L441-10 Code de Commerce.",
    }
    label    = {1: "Relance Amicale", 2: "Relance Ferme", 3: "Mise en Demeure"}
    due      = row.get("Date Echeance", "N/A")
    due_str  = due.strftime("%d/%m/%Y") if pd.notna(due) and hasattr(due, "strftime") else str(due)
    montant  = float(row.get("Montant", 0))
    client   = str(row.get("Client", ""))
    categorie   = get_categorie(montant)
    nb_relances = compter_relances_client(client)

    contexte_client = {
        "petit":     "petit montant, client probablement particulier ou tres petite structure",
        "normal":    "montant standard, client PME classique",
        "important": "montant eleve, client strategique a menager",
    }.get(categorie, "")

    if nb_relances == 0:
        historique_client = "C'est la premiere relance, sois particulierement courtois."
    elif nb_relances == 1:
        historique_client = "Ce client a deja recu une relance sans repondre, sois plus ferme."
    else:
        historique_client = f"Ce client a deja recu {nb_relances} relances sans repondre, sois tres ferme."

    prompt = f"""Tu es le service comptabilite d une PME francaise.
Redige un email de relance avec le ton suivant : {tone[niveau]}

Donnees de la facture :
- Numero : {row.get("Numero Facture", "N/A")}
- Client : {client}
- Montant du : {round(montant, 2)} EUR
- Echeance : {due_str}
- Retard : {row.get("Jours Retard", 0)} jours
- Type : {label[niveau]}

Contexte client : {contexte_client}
Historique : {historique_client}

Regles :
- Francais professionnel
- Commence par Objet : puis le corps du mail
- Termine par Le Service Comptabilite
- Email complet et pret a envoyer, aucun placeholder

Fournis UNIQUEMENT l email, rien d autre."""

    ai  = anthropic.Anthropic()
    msg = ai.messages.create(
        model="claude-opus-4-5",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text

def envoyer_email(expediteur: str, mot_de_passe: str,
                  destinataire: str, email_text: str) -> bool:
    lignes = email_text.strip().split("\n")
    sujet  = "Relance facture impayee - KOLO"
    corps  = email_text
    for i, ligne in enumerate(lignes):
        if ligne.lower().startswith("objet"):
            sujet = ligne.split(":", 1)[-1].strip()
            corps = "\n".join(lignes[i+1:]).strip()
            break
    msg = MIMEMultipart("alternative")
    msg["Subject"] = sujet
    msg["From"]    = expediteur
    msg["To"]      = destinataire
    msg.attach(MIMEText(corps, "plain", "utf-8"))
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode    = ssl.CERT_NONE
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(expediteur, mot_de_passe)
        server.sendmail(expediteur, destinataire, msg.as_string())
    return True

def lancer_relances_automatiques():
    print(f"\n{'='*50}")
    print(f"[KOLO] Lancement relances automatiques - {date.today().strftime('%d/%m/%Y')}")
    print(f"{'='*50}")
    config = charger_config()
    if not config:
        print("[ERREUR] Aucune configuration trouvee.")
        return
    gmail_user = config.get("gmail_user", "")
    gmail_pass = config.get("gmail_pass", "")
    dossier    = config.get("dossier_surveille", "")
    api_key    = config.get("anthropic_api_key", "")
    if api_key:
        os.environ["ANTHROPIC_API_KEY"] = api_key
    if not all([gmail_user, gmail_pass, dossier]):
        print("[ERREUR] Configuration incomplete.")
        return
    print(f"[INFO] Scan du dossier : {dossier}")
    df = scanner_dossier(dossier)
    if df.empty:
        print("[INFO] Aucun fichier a traiter.")
        return
    df = normaliser_colonnes(df)
    s = df.get("Statut", pd.Series(dtype=str)).str.strip().str.lower()
    df_impayees = df[s.isin(["impaye", "impaye"])].copy()
    df_impayees = df_impayees[df_impayees.get("Jours Retard", 0) >= 3]
    print(f"[INFO] {len(df_impayees)} facture(s) impayee(s) trouvee(s)")
    envoyes = 0
    ignores = 0
    for _, row in df_impayees.iterrows():
        jours   = int(row.get("Jours Retard", 0))
        montant = float(row.get("Montant", 0))
        client  = str(row.get("Client", ""))
        niveau  = determiner_niveau(jours, montant, client)
        numero  = str(row.get("Numero Facture", "N/A"))
        email   = row.get("Email Client", "")
        if niveau == 0:
            continue
        if deja_relance(numero, niveau):
            print(f"[IGNORE] {numero} - {client} : Niveau {niveau} deja envoye")
            ignores += 1
            continue
        if not email or pd.isna(email):
            print(f"[IGNORE] {numero} - {client} : Pas d email")
            ajouter_historique(row, niveau, "Echec : email manquant")
            ignores += 1
            continue
        try:
            print(f"[ENVOI] {numero} - {client} - Niveau {niveau} - {jours}j de retard")
            email_text = generer_email(row, niveau)
            envoyer_email(gmail_user, gmail_pass, email, email_text)
            ajouter_historique(row, niveau, "Envoye")
            envoyes += 1
            print(f"[OK] Email envoye a {email}")
            time.sleep(3)
        except Exception as e:
            print(f"[ERREUR] {numero} - {client} : {e}")
            ajouter_historique(row, niveau, f"Echec : {e}")
    print(f"\n[RESUME] {envoyes} email(s) envoye(s), {ignores} ignore(s)")
    print(f"{'='*50}\n")

if __name__ == "__main__":
    print(f"[KOLO] Scheduler demarre - Relances programmees a {HEURE_ENVOI} chaque jour")
    print("[KOLO] Regles : Petit < 1000 euros | Normal 1000-5000 euros | Important > 5000 euros")
    print("[KOLO] Appuie sur Ctrl+C pour arreter\n")
    schedule.every().day.at(HEURE_ENVOI).do(lancer_relances_automatiques)
    print("[KOLO] Premier lancement immediat pour verification...")
    lancer_relances_automatiques()
    while True:
        schedule.run_pending()
        time.sleep(60)