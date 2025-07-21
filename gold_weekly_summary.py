import requests
from bs4 import BeautifulSoup
from datetime import datetime
import nltk
from nltk.tokenize import sent_tokenize
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lsa import LsaSummarizer

# Télécharger les ressources NLTK nécessaires
nltk.download('punkt')

# Liens d’articles fiables sur l’or
articles = [
    "https://www.reuters.com/world/china/gold-gains-softer-dollar-investors-await-us-trade-updates-2025-07-21/",
    "https://www.reuters.com/world/china/gold-heads-weekly-dip-firm-dollar-platinum-highest-since-2014-2025-07-18/"
]

def extract_article_text(url):
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        paragraphs = soup.find_all('p')
        text = '\n'.join(p.get_text() for p in paragraphs)
        return text.strip()
    except Exception as e:
        return f"[Erreur extraction article] {e}"

def summarize_text(text, sentences_count=4):
    parser = PlaintextParser.from_string(text, Tokenizer("french"))
    summarizer = LsaSummarizer()
    summary = summarizer(parser.document, sentences_count)
    return "\n".join(str(sentence) for sentence in summary)

# Préparer les résumés à partir des articles
all_summaries = []

for url in articles:
    text = extract_article_text(url)
    if "Erreur" not in text:
        try:
            summary = summarize_text(text, 4)
            all_summaries.append(f"🔗 Source : {url}\n{summary}")
        except Exception as e:
            all_summaries.append(f"❌ Erreur résumé : {e}\n🔗 {url}")
    else:
        all_summaries.append(f"❌ {text}")

# Composer le message Discord
message = f"""📊 **Résumé hebdomadaire du marché de l'or** – {datetime.now().strftime('%d/%m/%Y')}

🕵️‍♂️ **Analyse automatique basée sur 2 articles récents :**

{chr(10).join(all_summaries)}

🧠 Résumé généré automatiquement. À vérifier avant diffusion officielle.
"""

# Webhook Discord (à personnaliser avec ton lien)
WEBHOOK_URL = "https://discord.com/api/webhooks/1396818376852242495/m-F9GOn6oiqALUjqP6GZ9xycTk-pV9ie2fGA9KDk3J6aKxKQVKJZzipG2l0zAw5fNAMx"

# Envoi du message vers Discord
try:
    MAX_LENGTH = 1900  # Discord limite à 2000 caractères max
    if len(message) > MAX_LENGTH:
        print("⚠️ Message trop long, découpage automatique en deux parties.")
        part1 = message[:MAX_LENGTH]
        part2 = message[MAX_LENGTH:]

        # Envoyer les deux morceaux
        r1 = requests.post(WEBHOOK_URL, json={"content": part1})
        r2 = requests.post(WEBHOOK_URL, json={"content": part2})
        if r1.status_code == 204 and r2.status_code == 204:
            print("✅ Résumé complet envoyé en deux parties.")
        else:
            print(f"❌ Erreur d'envoi Discord (part1: {r1.status_code}, part2: {r2.status_code})")
    else:
        response = requests.post(WEBHOOK_URL, json={"content": message})
        if response.status_code == 204:
            print("✅ Résumé envoyé avec succès à Discord.")
        else:
            print(f"❌ Erreur d'envoi Discord : {response.status_code} — {response.text}")
except Exception as e:
    print(f"❌ Exception Discord : {e}")
