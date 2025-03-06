# -*- coding: utf-8 -*-

import wikipediaapi
import google.generativeai as genai
import gradio as gr
import random
import re
import os
from dotenv import load_dotenv  # Import pour charger les variables d'environnement
from typing import Optional, Dict, List

# Charger les variables d'environnement depuis le fichier .env
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")  # Récupère la clé API depuis le fichier .env

# Vérifier si la clé API est bien chargée
if not API_KEY:
    raise ValueError("⚠️ Clé API GEMINI introuvable ! Assurez-vous d'avoir un fichier .env avec GEMINI_API_KEY.")


# Configuration API
genai.configure(api_key=API_KEY)
wiki = wikipediaapi.Wikipedia(language='fr', user_agent="CelebrityGame/1.0")

# Nom de la catégorie à utiliser (vérifiez bien le nom exact sur Wikipedia)
CATEGORY_NAME = "Catégorie:Personnalité masculine"

def get_category_members(category: wikipediaapi.WikipediaPage, depth: int = 1) -> List[wikipediaapi.WikipediaPage]:
    members = []
    for member in category.categorymembers.values():
        if member.ns == 0:
            members.append(member)
        elif depth > 0 and member.ns == 14:  # 14 correspond aux pages de catégorie
            subcat = wiki.page(member.title)
            members.extend(get_category_members(subcat, depth=depth - 1))
    return members

def get_random_celebritiy() -> Optional[str]:
    try:
        category = wiki.page(CATEGORY_NAME)
        if not category.exists():
            print(f"Catégorie Wikipedia introuvable : {CATEGORY_NAME}")
            return None

        members = get_category_members(category, depth=1)
        print(f"Nombre de membres trouvés dans la catégorie '{CATEGORY_NAME}': {len(members)}")
        if not members:
            print("Aucun membre trouvé dans la catégorie.")
            return None

        return random.choice(members).title
    except Exception as e:
        print(f"Erreur Wikipedia: {str(e)}")
        return None

def get_celebritiy_info(name: str) -> Optional[Dict]:
    try:
        page = wiki.page(name)
        if page.exists():
            return {
                "name": name,
                "summary": page.summary[:2000] if page.summary else "",
                "url": page.fullurl
            }
        else:
            print(f"La page pour {name} n'existe pas.")
            return None
    except Exception as e:
        print(f"Erreur récupération info: {str(e)}")
        return None

def create_game_session() -> Optional[Dict]:
    try:
        celeb = get_random_celebritiy()
        if celeb:
            return get_celebritiy_info(celeb)
        return None
    except Exception as e:
        print(f"Erreur création session: {str(e)}")
        return None

def ask_model(question: str, context: Dict, model_choice: str = "gemini") -> str:
    try:
        prompt = f"""
Rôle: Vous connaissez la célébrité suivante: {context.get('name', 'Inconnu')}
Informations: {context.get('summary', 'Aucune information')}

Règles strictes:
1. Répondez uniquement par 'oui' ou 'non'
2. Ne révélez jamais le nom directement
3. Si incertain, répondez 'Je ne sais pas'

Question: {question}
Réponse:
"""
        if model_choice == "gemini":
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(prompt)
            answer = response.text.lower().strip()[:50]  # Limite la longueur de la réponse
        elif model_choice == "claude":
            if "homme" in question.lower():
                answer = "oui"
            else:
                answer = "non"
        else:
            answer = "modèle non supporté"
        return answer
    except Exception as e:
        print(f"Erreur modèle IA: {str(e)}")
        return "Erreur de réponse"

# Interface Gradio avec gestion d'états
with gr.Blocks(theme=gr.themes.Soft()) as app:
    game_state = gr.State(None)
    chatbot = gr.Chatbot(height=800)

    # Sélecteur de modèle IA
    model_selector = gr.Radio(
        choices=["Gemini 1.5 Flash", "Claude"],
        label="Sélectionnez le modèle IA",
        value="Gemini 1.5 Flash"
    )
    
    def start_new_game(model_choice: str):
        game_data = create_game_session()
        if game_data:
            chosen_model = "gemini" if model_choice.lower().startswith("gemini") else "claude"
            game_data["model"] = chosen_model
            return game_data, []
        return None, [("Système", "❌ Impossible de démarrer une nouvelle partie")]
    
    def handle_question(question: str, history: list, game_data: Optional[Dict]):
        if not game_data:
            return history + [("Système", "⚠️ Commencez une nouvelle partie d'abord !")], "", None
        
        clean_question = re.sub(r'[^\w\s]', '', question).strip().lower()
        if not clean_question:
            return history, "", game_data
        
        if game_data['name'].lower() in clean_question:
            victory_msg = f"🎉 Bravo ! Vous avez trouvé : {game_data['name']}"
            return history + [(question, victory_msg)], "", None
        
        response = ask_model(clean_question, game_data, game_data.get("model", "gemini"))
        if "oui" in response:
            formatted_response = "✅ OUI"
        elif "non" in response:
            formatted_response = "❌ NON"
        else:
            formatted_response = "🤷 Je ne peux pas répondre"
        
        return history + [(question, formatted_response)], "", game_data

    def reveal_answer(game_data: Optional[Dict], history: list):
        """Révèle la célébrité et termine la partie."""
        if not game_data:
            return history, None
        new_history = history + [("J'abandonne", f"🔍 La réponse était : {game_data['name']}\n🌐 {game_data['url']}")]
        return new_history, None

    gr.Markdown("# 🕵️♂️ Devine la Célébrité avec l'IA")
    
    with gr.Row():
        start_btn = gr.Button("🚀 Nouvelle Partie", variant="primary")
        giveup_btn = gr.Button("🏳️ Abandonner")
    
    question_input = gr.Textbox(label="Posez votre question", placeholder="Ex: Est-ce un homme ?")
    
    start_btn.click(
        start_new_game,
        inputs=[model_selector],
        outputs=[game_state, chatbot]
    )
    
    question_input.submit(
        handle_question,
        inputs=[question_input, chatbot, game_state],
        outputs=[chatbot, question_input, game_state]
    )
    
    giveup_btn.click(
        reveal_answer,
        inputs=[game_state, chatbot],
        outputs=[chatbot, game_state]
    )

app.launch(show_error=True)
