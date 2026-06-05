"""
KOLO - MVP v3.0
Nouveautes : comptes utilisateurs, connexion Supabase
"""

import streamlit as st
import pandas as pd
from datetime import date, timedelta
import io
import os
import smtplib
import ssl
import httpx
import hashlib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import anthropic
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.enums import TA_LEFT, TA_CENTER
import plotly.express as px
from PIL import Image
import base64
import json

# ─── CONFIGURATION SUPABASE ──────────────────────────────────────
SUPABASE_URL = st.secrets.get("SUPABASE_URL", os.environ.get("SUPABASE_URL", ""))
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", os.environ.get("SUPABASE_KEY", ""))

def supabase_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }

def hasher_mot_de_passe(mdp: str) -> str:
    return hashlib.sha256(mdp.encode()).hexdigest()

def creer_compte(email: str, mdp: str, nom_entreprise: str) -> dict:
    url = f"{SUPABASE_URL}/rest/v1/utilisateurs"
    data = {
        "email": email,
        "mot_de_passe": hasher_mot_de_passe(mdp),
        "nom_entreprise": nom_entreprise,
        "date_inscription": date.today().strftime("%d/%m/%Y"),
    }
    r = httpx.post(url, headers=supabase_headers(), json=data)
    if r.status_code in [200, 201]:
        return {"succes": True}
    else:
        return {"succes": False, "erreur": r.text}

def connecter_utilisateur(email: str, mdp: str) -> dict:
    url = f"{SUPABASE_URL}/rest/v1/utilisateurs?email=eq.{email}&mot_de_passe=eq.{hasher_mot_de_passe(mdp)}"
    r = httpx.get(url, headers=supabase_headers())
    if r.status_code == 200 and len(r.json()) > 0:
        return {"succes": True, "utilisateur": r.json()[0]}
    else:
        return {"succes": False}

def email_existe(email: str) -> bool:
    url = f"{SUPABASE_URL}/rest/v1/utilisateurs?email=eq.{email}"
    r = httpx.get(url, headers=supabase_headers())
    return r.status_code == 200 and len(r.json()) > 0


# ─── PAGE CONFIG ─────────────────────────────────────────────────
try:
    icon = Image.open("logo.png")
    st.set_page_config(page_title="KOLO", page_icon=icon, layout="wide", initial_sidebar_state="collapsed")
except:
    st.set_page_config(page_title="KOLO", page_icon="💰", layout="wide", initial_sidebar_state="collapsed")

# ─── CSS ─────────────────────────────────────────────────────────
st.markdown("""
<style>
    html, body, [class*="css"] { font-family: 'Inter', 'Segoe UI', sans-serif; }
    .stApp { background-color: #F5ECD7 !important; }
    section.main { background-color: #F5ECD7 !important; }
    .block-container { background-color: #F5ECD7 !important; }
    .hero {
        background: linear-gradient(135deg, #1B2A4A 0%, #2E4A7A 100%);
        padding: 2rem 2.5rem; border-radius: 16px;
        margin-bottom: 2rem; color: white;
    }
    .hero h1 { font-size: 2.2rem; font-weight: 800; margin: 0; }
    .hero p  { font-size: 1rem; opacity: 0.85; margin: 0.4rem 0 0; }
    .metric-card {
        background: white; border-radius: 12px;
        padding: 1.2rem 1.5rem;
        box-shadow: 0 2px 8px rgba(27,42,74,0.08);
        border-left: 4px solid #2E4A7A;
    }
    .metric-card h3 { margin:0; font-size:0.8rem; color:#6B7280; text-transform:uppercase; }
    .metric-card p  { margin:0.3rem 0 0; font-size:1.8rem; font-weight:700; color:#1B2A4A; }
    .email-box {
        background: white; border-radius: 12px;
        border: 1px solid #E5E7EB; padding: 1.5rem;
        white-space: pre-wrap; font-family: 'Courier New', monospace;
        font-size: 0.88rem; line-height: 1.7; color: #1F2937;
    }
    .login-box {
        background: white; border-radius: 16px;
        padding: 2.5rem; max-width: 450px;
        margin: 2rem auto;
        box-shadow: 0 4px 20px rgba(27,42,74,0.12);
    }
    .stButton > button {
        background: #1B2A4A !important; color: white !important;
        border: none; border-radius: 8px; font-weight: 600;
        width: 100%;
    }
    .stButton > button:hover { background: #2E4A7A !important; }
    #MainMenu, footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


# ─── LOGO ────────────────────────────────────────────────────────
def get_logo_base64():
    try:
        with open("logo.png", "rb") as f:
            return base64.b64encode(f.read()).decode()
    except:
        return None

logo_b64 = get_logo_base64()
logo_html = f'<img src="data:image/png;base64,{logo_b64}" style="height:100px;margin-bottom:0.5rem;">' if logo_b64 else "💰"


# ─── GESTION SESSION ─────────────────────────────────────────────
if "connecte" not in st.session_state:
    st.session_state["connecte"] = False
if "utilisateur" not in st.session_state:
    st.session_state["utilisateur"] = None


# ════════════════════════════════════════════════════════════════
# PAGE CONNEXION / INSCRIPTION
# ════════════════════════════════════════════════════════════════
if not st.session_state["connecte"]:

    st.markdown(f"""
    <div style="text-align:center;padding:2rem 0 1rem;">
        {logo_html}
        <h1 style="color:#1B2A4A;font-size:2.5rem;font-weight:800;margin:0.5rem 0 0;">KOLO</h1>
        <p style="color:#6B7280;font-size:1rem;">Votre tresorerie, simplifiee</p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        onglet = st.radio("", ["Se connecter", "Creer un compte"], horizontal=True)

        st.markdown("---")

        if onglet == "Se connecter":
            email    = st.text_input("Email", placeholder="toi@exemple.fr", key="login_email")
            mdp      = st.text_input("Mot de passe", type="password", key="login_mdp")

            if st.button("Se connecter", use_container_width=True):
                if email and mdp:
                    with st.spinner("Connexion en cours..."):
                        result = connecter_utilisateur(email, mdp)
                    if result["succes"]:
                        st.session_state["connecte"]    = True
                        st.session_state["utilisateur"] = result["utilisateur"]
                        st.rerun()
                    else:
                        st.error("Email ou mot de passe incorrect")
                else:
                    st.warning("Remplis tous les champs")

        else:
            # Code d'invitation valides — ajoute ou supprime des codes ici
            CODES_VALIDES = ["KOLO2026", "BETA30", "KOLOMAI"]

            nom_entreprise = st.text_input("Nom de votre entreprise", placeholder="Ma Societe SAS", key="reg_entreprise")
            email          = st.text_input("Email", placeholder="toi@exemple.fr", key="reg_email")
            mdp            = st.text_input("Mot de passe", type="password", key="reg_mdp")
            mdp2           = st.text_input("Confirmer le mot de passe", type="password", key="reg_mdp2")
            code           = st.text_input("Code d'invitation", placeholder="Ex: KOLO2026", key="reg_code")
            st.caption("Vous n'avez pas de code ? Contactez-nous sur LinkedIn.")

            if st.button("Creer mon compte", use_container_width=True):
                if all([nom_entreprise, email, mdp, mdp2, code]):
                    if code.strip().upper() not in CODES_VALIDES:
                        st.error("Code d'invitation invalide. Contactez-nous pour en obtenir un.")
                    elif mdp != mdp2:
                        st.error("Les mots de passe ne correspondent pas")
                    elif len(mdp) < 6:
                        st.error("Le mot de passe doit faire au moins 6 caracteres")
                    elif email_existe(email):
                        st.error("Cet email est deja utilise")
                    else:
                        with st.spinner("Creation du compte..."):
                            result = creer_compte(email, mdp, nom_entreprise)
                        if result["succes"]:
                            st.success("Compte cree ! Connecte-toi maintenant.")
                        else:
                            st.error(f"Erreur : {result.get('erreur', 'Inconnue')}")
                else:
                    st.warning("Remplis tous les champs including le code d'invitation")

    st.markdown("""
    <div style="text-align:center;padding:2rem 0 1rem;color:#D1D5DB;font-size:0.78rem;">
        KOLO v3.0 - Propulse par Claude AI
    </div>
    """, unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════
# APPLICATION PRINCIPALE (apres connexion)
# ════════════════════════════════════════════════════════════════
else:
    utilisateur = st.session_state["utilisateur"]
    nom_entreprise_connecte = utilisateur.get("nom_entreprise", "")

    # ─── FICHIER HISTORIQUE PAR UTILISATEUR ──────────────────────
    user_id = utilisateur.get("id", utilisateur.get("email", "default"))
    HISTORIQUE_FILE = f"historique_{user_id}.xlsx"

    def charger_historique() -> pd.DataFrame:
        if os.path.exists(HISTORIQUE_FILE):
            return pd.read_excel(HISTORIQUE_FILE)
        return pd.DataFrame(columns=[
            "Date Envoi", "Numero Facture", "Client",
            "Montant", "Jours Retard", "Niveau", "Email Client", "Statut Envoi"
        ])

    def charger_historique() -> pd.DataFrame:
        """Charge l'historique depuis Supabase pour cet utilisateur."""
        try:
            url = f"{SUPABASE_URL}/rest/v1/historique?user_email=eq.{utilisateur['email']}&order=date_envoi.desc"
            r = httpx.get(url, headers=supabase_headers())
            if r.status_code == 200 and len(r.json()) > 0:
                df = pd.DataFrame(r.json())
                df = df.rename(columns={
                    "date_envoi":      "Date Envoi",
                    "numero_facture":  "Numero Facture",
                    "client":          "Client",
                    "montant":         "Montant",
                    "jours_retard":    "Jours Retard",
                    "niveau":          "Niveau",
                    "email_client":    "Email Client",
                    "statut_envoi":    "Statut Envoi",
                })
                cols = ["Date Envoi","Numero Facture","Client","Montant","Jours Retard","Niveau","Email Client","Statut Envoi"]
                return df[[c for c in cols if c in df.columns]]
            return pd.DataFrame(columns=["Date Envoi","Numero Facture","Client","Montant","Jours Retard","Niveau","Email Client","Statut Envoi"])
        except Exception as e:
            st.error(f"Erreur chargement historique : {e}")
            return pd.DataFrame(columns=["Date Envoi","Numero Facture","Client","Montant","Jours Retard","Niveau","Email Client","Statut Envoi"])

    def sauvegarder_historique(df: pd.DataFrame):
        """Inutile avec Supabase - on sauvegarde ligne par ligne."""
        pass

    def ajouter_historique(row: pd.Series, niveau: int, statut: str):
        """Ajoute une ligne dans Supabase."""
        try:
            url = f"{SUPABASE_URL}/rest/v1/historique"
            data = {
                "user_email":     utilisateur["email"],
                "date_envoi":     date.today().strftime("%d/%m/%Y"),
                "numero_facture": str(row.get("Numero Facture", "N/A")),
                "client":         str(row.get("Client", "N/A")),
                "montant":        float(row.get("Montant", 0)),
                "jours_retard":   int(row.get("Jours Retard", 0)),
                "niveau":         f"Niveau {niveau}",
                "email_client":   str(row.get("Email Client", "N/A")),
                "statut_envoi":   statut,
            }
            httpx.post(url, headers=supabase_headers(), json=data)
        except Exception as e:
            st.error(f"Erreur sauvegarde historique : {e}")

    def get_categorie(montant: float) -> str:
        if montant < 1000:   return "petit"
        elif montant < 5000: return "normal"
        else:                return "important"

    def compter_relances_historique(client: str) -> int:
        """Compte les relances depuis Supabase pour ce client."""
        try:
            url = f"{SUPABASE_URL}/rest/v1/historique?user_email=eq.{utilisateur['email']}&client=eq.{client}&statut_envoi=eq.Envoye"
            r = httpx.get(url, headers=supabase_headers())
            if r.status_code == 200:
                return len(r.json())
            return 0
        except:
            return 0

    # ─── EXPORT PDF ──────────────────────────────────────────────
    def generer_pdf(email_text: str, row: pd.Series, niveau: int) -> bytes:
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4,
            rightMargin=2*cm, leftMargin=2*cm,
            topMargin=2*cm, bottomMargin=2*cm)
        styles = getSampleStyleSheet()
        style_titre = ParagraphStyle("titre", parent=styles["Normal"],
            fontSize=16, fontName="Helvetica-Bold",
            alignment=TA_CENTER, spaceAfter=20)
        style_sous_titre = ParagraphStyle("sous_titre", parent=styles["Normal"],
            fontSize=11, fontName="Helvetica-Bold",
            alignment=TA_CENTER, spaceAfter=30)
        style_corps = ParagraphStyle("corps", parent=styles["Normal"],
            fontSize=10, fontName="Helvetica",
            leading=16, spaceAfter=12, alignment=TA_LEFT)
        style_footer = ParagraphStyle("footer", parent=styles["Normal"],
            fontSize=8, fontName="Helvetica",
            alignment=TA_CENTER, textColor="grey")
        niveau_label = {1: "Relance Niveau 1", 2: "Relance Niveau 2", 3: "MISE EN DEMEURE"}
        contenu = []
        contenu.append(Paragraph("KOLO", style_titre))
        contenu.append(Paragraph(niveau_label.get(niveau, "Relance"), style_sous_titre))
        contenu.append(Spacer(1, 0.5*cm))
        for ligne in email_text.split("\n"):
            if ligne.strip():
                contenu.append(Paragraph(
                    ligne.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"),
                    style_corps))
            else:
                contenu.append(Spacer(1, 0.3*cm))
        contenu.append(Spacer(1, 1*cm))
        contenu.append(Paragraph(
            f"Document genere le {date.today().strftime('%d/%m/%Y')} par KOLO",
            style_footer))
        doc.build(contenu)
        return buf.getvalue()

    # ─── ENVOI GMAIL ─────────────────────────────────────────────
    def envoyer_email_gmail(expediteur, mot_de_passe, destinataire, email_text):
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

    # ─── CHARGEMENT FICHIER ──────────────────────────────────────
    def generate_sample_excel() -> bytes:
        today = date.today()
        data = {
            "Numero Facture": ["FAC-2025-001","FAC-2025-002","FAC-2025-003","FAC-2025-004","FAC-2025-005","FAC-2025-006"],
            "Client": ["SARL Dupont et Fils","SAS Tech Innovate","Auto-Entrepreneur Martin","EURL Bati Plus","SA Logistique Express","Micro-Entreprise Leroy"],
            "Email Client": ["contact@dupont-fils.fr","info@techinnovate.fr","p.martin@email.fr","batiplus@pro.fr","compta@logistique-exp.fr","leroy.jean@email.fr"],
            "Montant euros": [4850.00, 12300.00, 680.00, 3200.00, 8750.00, 1150.00],
            "Date Emission": [str(today-timedelta(days=55)),str(today-timedelta(days=40)),str(today-timedelta(days=25)),str(today-timedelta(days=60)),str(today-timedelta(days=20)),str(today-timedelta(days=15))],
            "Date Echeance": [str(today-timedelta(days=25)),str(today-timedelta(days=10)),str(today+timedelta(days=5)),str(today-timedelta(days=45)),str(today-timedelta(days=3)),str(today+timedelta(days=15))],
            "Statut": ["Impaye","Impaye","Impaye","Impaye","Paye","Impaye"],
        }
        df = pd.DataFrame(data)
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Factures")
        return buf.getvalue()

    def load_and_analyze(file) -> pd.DataFrame:
        if file.name.lower().endswith(".csv"):
            df = pd.read_csv(file, sep=None, engine="python")
        else:
            df = pd.read_excel(file)
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
                lambda x: max(0, int(x)) if pd.notna(x) else 0)
        def compute_niveau(j):
            if j <= 15:   return 1
            elif j <= 30: return 2
            else:         return 3
        if "Jours Retard" in df.columns:
            df["Niveau"] = df["Jours Retard"].apply(compute_niveau)
        return df

    def filter_overdue(df: pd.DataFrame) -> pd.DataFrame:
        df = df.reset_index(drop=True)
        if "Statut" not in df.columns:
            return pd.DataFrame()
        mask_s = df["Statut"].astype(str).str.strip().str.lower().isin(["impaye", "impayé"])
        if "Jours Retard" not in df.columns:
            return pd.DataFrame()
        mask_r = df["Jours Retard"] > 0
        return df[mask_s & mask_r].copy()

    # ─── GENERATION EMAIL ────────────────────────────────────────
    def generate_email(row, niveau, nom_entreprise="", nom_signataire="", telephone=""):
        tone = {
            1: "tres courtois et chaleureux, suggere poliment qu'il s'agit d'un oubli.",
            2: "professionnel et serieux, deuxieme rappel, rappelle les consequences sans agressivite.",
            3: "juridique et strict, mise en demeure formelle, mentionne les penalites legales art L441-10 Code de Commerce.",
        }
        label = {1: "Relance Amicale", 2: "Relance Ferme", 3: "Mise en Demeure"}
        due     = row.get("Date Echeance", "N/A")
        due_str = due.strftime("%d/%m/%Y") if pd.notna(due) and hasattr(due, "strftime") else str(due)
        montant = float(row.get("Montant", 0))
        client  = str(row.get("Client", ""))
        categorie   = get_categorie(montant)
        nb_relances = compter_relances_historique(client)
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

Informations expediteur :
- Entreprise : {nom_entreprise if nom_entreprise else "Notre entreprise"}
- Signataire : {nom_signataire if nom_signataire else "Le Service Comptabilite"}
- Telephone : {telephone if telephone else ""}

Regles :
- Francais professionnel
- Commence par Objet : puis le corps du mail
- Termine par le nom de l entreprise et du signataire
- Email complet et pret a envoyer, aucun placeholder

Fournis UNIQUEMENT l email, rien d autre."""

        ai  = anthropic.Anthropic()
        msg = ai.messages.create(
            model="claude-opus-4-5",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text

    # ════════════════════════════════════════════════════════════
    # INTERFACE PRINCIPALE
    # ════════════════════════════════════════════════════════════

    # Header
    st.markdown(f"""
    <div class="hero">
        <div style="display:flex;align-items:center;justify-content:space-between;">
            <div style="display:flex;align-items:center;gap:1.5rem;">
                <div>{logo_html}</div>
                <div>
                    <h1 style="margin:0;font-size:2.2rem;font-weight:800;">KOLO</h1>
                    <p style="margin:0;opacity:0.85;font-size:1rem;">Votre tresorerie, simplifiee</p>
                </div>
            </div>
            <div style="text-align:right;opacity:0.85;font-size:0.9rem;">
                Bonjour {nom_entreprise_connecte} 👋
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Sidebar
    with st.sidebar:
        st.markdown(f"### Bonjour {nom_entreprise_connecte} !")
        st.markdown(f"*{utilisateur.get('email', '')}*")
        if st.button("Se deconnecter", use_container_width=True):
            st.session_state["connecte"]    = False
            st.session_state["utilisateur"] = None
            st.rerun()

        st.markdown("---")
        st.markdown("### Configuration Gmail")
        gmail_user = st.text_input("Votre adresse Gmail", placeholder="toi@gmail.com", key="sidebar_gmail_user")
        gmail_pass = st.text_input("Mot de passe application Gmail", type="password", placeholder="xxxx xxxx xxxx xxxx", key="sidebar_gmail_pass")
        gmail_ok   = bool(gmail_user and gmail_pass)

        st.markdown("---")
        st.markdown("### Votre entreprise")
        nom_entreprise = st.text_input("Nom de votre entreprise", value=nom_entreprise_connecte, key="sidebar_entreprise")
        nom_signataire = st.text_input("Votre nom", placeholder="Jean Dupont", key="sidebar_signataire")
        telephone      = st.text_input("Telephone", placeholder="01 23 45 67 89", key="sidebar_telephone")

        st.markdown("---")
        st.markdown("### Relances automatiques")
        dossier_surveille = st.text_input(
            "Dossier a surveiller",
            placeholder=r"C:\Users\Jeremy\Documents\Factures",
            key="sidebar_dossier"
        )
        if st.button("Sauvegarder la configuration", use_container_width=True):
            if gmail_user and gmail_pass and dossier_surveille:
                config = {
                    "gmail_user": gmail_user,
                    "gmail_pass": gmail_pass,
                    "dossier_surveille": dossier_surveille,
                }
                with open("KOLO_config.json", "w") as f:
                    json.dump(config, f, indent=2)
                st.success("Configuration sauvegardee !")
            else:
                st.error("Remplis tous les champs")

        if gmail_ok:
            st.success("Gmail configure !")
        else:
            st.warning("Remplis Gmail pour activer l'envoi")

    # Onglets
    tab1, tab2, tab3 = st.tabs(["Relances", "Tableau de bord", "Historique"])

    with tab1:
        with st.expander("Pas de fichier ? Telechargez notre fichier de demonstration"):
            st.download_button(
                "Telecharger le fichier Excel de test",
                data=generate_sample_excel(),
                file_name="factures_test_KOLO.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

        st.markdown("### Importez votre fichier de factures")
        uploaded_file = st.file_uploader("Formats : Excel (.xlsx, .xls) ou CSV (.csv)", type=["xlsx","xls","csv"], label_visibility="collapsed")

        if uploaded_file:
            with st.spinner("Analyse du fichier en cours..."):
                try:
                    df_all = load_and_analyze(uploaded_file)
                    df_ov  = filter_overdue(df_all)
                except Exception as e:
                    st.error(f"Erreur de lecture : {e}")
                    st.stop()

            c1, c2, c3, c4 = st.columns(4)
            amt = df_ov["Montant"].sum() if "Montant" in df_ov.columns else 0
            avg = df_ov["Jours Retard"].mean() if not df_ov.empty else 0
            with c1: st.markdown(f'<div class="metric-card"><h3>Total factures</h3><p>{len(df_all)}</p></div>', unsafe_allow_html=True)
            with c2: st.markdown(f'<div class="metric-card"><h3>En retard</h3><p style="color:#B91C1C">{len(df_ov)}</p></div>', unsafe_allow_html=True)
            with c3: st.markdown(f'<div class="metric-card"><h3>Montant impaye</h3><p>{amt:,.0f} euros</p></div>', unsafe_allow_html=True)
            with c4: st.markdown(f'<div class="metric-card"><h3>Retard moyen</h3><p>{avg:.0f} jours</p></div>', unsafe_allow_html=True)

            st.markdown("---")
            st.markdown("### Factures impayees en retard")

            if df_ov.empty:
                st.success("Aucune facture en retard !")
            else:
                dcols = [c for c in ["Numero Facture","Client","Montant","Date Echeance","Jours Retard","Niveau"] if c in df_ov.columns]
                ddf = df_ov[dcols].copy()
                if "Date Echeance" in ddf.columns:
                    ddf["Date Echeance"] = ddf["Date Echeance"].dt.strftime("%d/%m/%Y")
                if "Montant" in ddf.columns:
                    ddf["Montant"] = ddf["Montant"].apply(lambda x: f"{x:,.2f} euros")
                if "Niveau" in ddf.columns:
                    ddf["Niveau"] = ddf["Niveau"].map({1:"Niveau 1 - Amical", 2:"Niveau 2 - Ferme", 3:"Niveau 3 - Formel"})
                st.dataframe(ddf, use_container_width=True, hide_index=True)

                st.markdown("---")
                st.markdown("### Generer et envoyer une relance")

                opts = df_ov["Numero Facture"].tolist() if "Numero Facture" in df_ov.columns else list(range(len(df_ov)))
                sel  = st.selectbox("Choisissez une facture :", opts)
                row  = df_ov[df_ov["Numero Facture"] == sel].iloc[0] if "Numero Facture" in df_ov.columns else df_ov.iloc[sel]

                ca, cb, cc = st.columns(3)
                with ca: st.info(f"**Client :** {row.get('Client', 'N/A')}")
                with cb:
                    m = row.get("Montant", 0)
                    st.info(f"**Montant :** {m:,.2f} euros")
                with cc: st.info(f"**Retard :** {row.get('Jours Retard', 0)} jours")

                email_dest        = row.get("Email Client", "")
                email_destinataire = st.text_input("Email du destinataire",
                    value=email_dest if pd.notna(email_dest) else "",
                    placeholder="client@exemple.fr")

                nlabels = {1:"Niveau 1 - Amical", 2:"Niveau 2 - Ferme", 3:"Niveau 3 - Formel (mise en demeure)"}
                cn, cb2 = st.columns([3, 1])
                with cn:
                    niv = st.radio("Niveau de relance :", [1,2,3],
                        format_func=lambda x: nlabels[x],
                        index=int(row.get("Niveau",1))-1,
                        horizontal=True)
                with cb2:
                    st.write(""); st.write("")
                    go = st.button("Generer l'email", use_container_width=True)

                if go:
                    with st.spinner("L'IA redige votre email..."):
                        try:
                            txt = generate_email(
                                row, niv,
                                nom_entreprise=st.session_state.get("sidebar_entreprise", ""),
                                nom_signataire=st.session_state.get("sidebar_signataire", ""),
                                telephone=st.session_state.get("sidebar_telephone", ""),
                            )
                            st.session_state["etxt"] = txt
                            st.session_state["einv"] = sel
                            st.session_state["eniv"] = niv
                        except Exception as e:
                            st.error(f"Erreur de generation : {e}")

                if "etxt" in st.session_state and st.session_state.get("einv") == sel:
                    txt       = st.session_state["etxt"]
                    niv_saved = st.session_state.get("eniv", niv)
                    st.markdown("#### Email genere")
                    st.markdown(f'<div class="email-box">{txt}</div>', unsafe_allow_html=True)

                    col_dl, col_pdf, col_send = st.columns(3)
                    with col_dl:
                        st.download_button("Telecharger (.txt)", data=txt.encode("utf-8"),
                            file_name=f"relance_{sel}.txt", mime="text/plain")
                    with col_pdf:
                        try:
                            pdf_bytes = generer_pdf(txt, row, niv_saved)
                            st.download_button("Telecharger PDF", data=pdf_bytes,
                                file_name=f"relance_{sel}.pdf", mime="application/pdf")
                        except Exception as e:
                            st.error(f"Erreur PDF : {e}")
                    with col_send:
                        if gmail_ok and email_destinataire:
                            if st.button("Envoyer par Gmail", use_container_width=True):
                                with st.spinner("Envoi en cours..."):
                                    try:
                                        envoyer_email_gmail(gmail_user, gmail_pass, email_destinataire, txt)
                                        ajouter_historique(row, niv_saved, "Envoye")
                                        st.success(f"Email envoye a {email_destinataire} !")
                                    except Exception as e:
                                        ajouter_historique(row, niv_saved, f"Echec : {e}")
                                        st.error(f"Echec envoi : {e}")
                        elif not gmail_ok:
                            st.warning("Configurez Gmail dans le menu a gauche")
                        else:
                            st.warning("Entrez l'email du destinataire")
        else:
            st.markdown("""
            <div style="text-align:center;padding:3rem 1rem;color:#9CA3AF;">
                <div style="font-size:4rem;">📄</div>
                <h3 style="color:#6B7280;">Importez un fichier pour commencer</h3>
            </div>""", unsafe_allow_html=True)

    with tab2:
        st.markdown("### Tableau de bord analytique")
        df_hist = charger_historique()
        if df_hist.empty:
            st.info("Aucune relance envoyee pour l'instant.")
        else:
            m1, m2, m3 = st.columns(3)
            total_envoyes = len(df_hist)
            total_montant = df_hist["Montant"].sum() if "Montant" in df_hist.columns else 0
            taux_succes   = len(df_hist[df_hist["Statut Envoi"]=="Envoye"]) / total_envoyes * 100 if total_envoyes > 0 else 0
            with m1: st.markdown(f'<div class="metric-card"><h3>Relances envoyees</h3><p>{total_envoyes}</p></div>', unsafe_allow_html=True)
            with m2: st.markdown(f'<div class="metric-card"><h3>Montant relance</h3><p>{total_montant:,.0f} euros</p></div>', unsafe_allow_html=True)
            with m3: st.markdown(f'<div class="metric-card"><h3>Taux de succes</h3><p>{taux_succes:.0f}%</p></div>', unsafe_allow_html=True)
            st.markdown("---")
            g1, g2 = st.columns(2)
            with g1:
                if "Niveau" in df_hist.columns:
                    counts = df_hist["Niveau"].value_counts().reset_index()
                    counts.columns = ["Niveau", "Nombre"]
                    fig1 = px.bar(counts, x="Niveau", y="Nombre", title="Relances par niveau",
                        color="Niveau", color_discrete_map={"Niveau 1":"#3B82F6","Niveau 2":"#F59E0B","Niveau 3":"#EF4444"})
                    fig1.update_layout(showlegend=False, plot_bgcolor="white")
                    st.plotly_chart(fig1, use_container_width=True)
            with g2:
                if "Date Envoi" in df_hist.columns and "Montant" in df_hist.columns:
                    df_time = df_hist.copy()
                    df_time["Date Envoi"] = pd.to_datetime(df_time["Date Envoi"], dayfirst=True, errors="coerce")
                    df_time = df_time.dropna(subset=["Date Envoi"]).groupby("Date Envoi")["Montant"].sum().reset_index()
                    fig2 = px.line(df_time, x="Date Envoi", y="Montant", title="Montants relances dans le temps", markers=True)
                    fig2.update_traces(line_color="#1B2A4A")
                    fig2.update_layout(plot_bgcolor="white")
                    st.plotly_chart(fig2, use_container_width=True)

    with tab3:
        st.markdown("### Historique des relances")
        df_hist = charger_historique()
        if df_hist.empty:
            st.info("Aucune relance dans l'historique.")
        else:
            st.dataframe(df_hist, use_container_width=True, hide_index=True)
            buf_hist = io.BytesIO()
            with pd.ExcelWriter(buf_hist, engine="openpyxl") as writer:
                df_hist.to_excel(writer, index=False)
            st.download_button("Telecharger l'historique (Excel)",
                data=buf_hist.getvalue(),
                file_name="historique_relances.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    st.markdown("""
    <div style="text-align:center;padding:2rem 0 1rem;color:#D1D5DB;font-size:0.78rem;">
        KOLO v3.0 - Propulse par Claude AI - Fait avec le coeur pour les PME francaises
    </div>""", unsafe_allow_html=True)
