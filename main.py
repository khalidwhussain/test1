import os
import re
import json
import threading
import webbrowser
import tkinter as tk
from tkinter import filedialog
from flask import Flask, jsonify, send_from_directory, render_template_string, request
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)
GAME_FOLDER = ""
progress_data = {
    "total": 0,
    "completed": 0
}

def clean_game_title(name):
    name = os.path.splitext(name)[0]
    name = re.sub(r'[-_]', ' ', name)
    name = re.sub(r'\b(v?\d+(\.\d+)?|MR[-\s]?Fix|VRP|Oculus|Meta|Beta|Demo|[rR])\b', '', name, flags=re.IGNORECASE)
    name = re.sub(r'[^\w\s]', '', name)
    return ' '.join(name.split()).strip()

def fetch_metadata_from_uploadvr(link, title):
    try:
        r = requests.get(link, timeout=12)
        soup = BeautifulSoup(r.text, "html.parser")
        h1 = soup.find("h1")
        real_title = h1.text.strip() if h1 else title
        desc = ""
        desc_tag = soup.find('meta', {'name': 'description'})
        if desc_tag and desc_tag.get('content'):
            desc = desc_tag['content'].strip()
        img_tag = soup.find('meta', {'property': 'og:image'})
        image = img_tag['content'] if img_tag else None

        genre = ""
        for label in soup.find_all(string=re.compile("Genre", re.I)):
            if label.parent and label.parent.find_next_sibling():
                genre = label.parent.find_next_sibling().get_text(strip=True)
                break
        if not genre:
            genre_span = soup.find("span", class_=re.compile("genre", re.I))
            if genre_span:
                genre = genre_span.get_text(strip=True)
        if not genre:
            genre_block = soup.find(lambda tag: tag.name in ["div", "li"] and "genre" in tag.text.lower())
            if genre_block:
                genre = genre_block.get_text(strip=True).split(":", 1)[-1].strip()

        trailer = ""
        iframe = soup.find('iframe', src=re.compile("youtube|vimeo", re.I))
        if iframe:
            trailer = iframe['src']

        return {
            "title": real_title,
            "description": desc,
            "image": image,
            "trailer": trailer,
            "genre": genre,
            "store_link": link,
        }
    except Exception as e:
        print(f"[UploadVR] Error for {title}: {e}")
    return None

def fetch_metadata_from_oculusdb(link, title):
    try:
        r = requests.get(link, timeout=12)
        soup = BeautifulSoup(r.text, "html.parser")
        h1 = soup.find("h1")
        real_title = h1.text.strip() if h1 else title
        desc = ""
        desc_tag = soup.find('meta', {'name': 'description'})
        if desc_tag and desc_tag.get('content'):
            desc = desc_tag['content'].strip()
        img_tag = soup.find('meta', {'property': 'og:image'})
        image = img_tag['content'] if img_tag else None

        genre = ""
        for label in soup.find_all(string=re.compile("Genre", re.I)):
            parent = label.parent
            if parent and parent.find_next_sibling():
                genre = parent.find_next_sibling().get_text(strip=True)
                break
        if not genre:
            genre_span = soup.find("span", class_=re.compile("genre", re.I))
            if genre_span:
                genre = genre_span.get_text(strip=True)
        if not genre:
            genre_block = soup.find(lambda tag: tag.name in ["div", "li"] and "genre" in tag.text.lower())
            if genre_block:
                genre = genre_block.get_text(strip=True).split(":", 1)[-1].strip()

        trailer = ""
        iframe = soup.find('iframe', src=re.compile("youtube|vimeo", re.I))
        if iframe:
            trailer = iframe['src']

        return {
            "title": real_title,
            "description": desc,
            "image": image,
            "trailer": trailer,
            "genre": genre,
            "store_link": link,
        }
    except Exception as e:
        print(f"[OculusDB] Error for {title}: {e}")
    return None

def fetch_metadata_from_vrdb(link, title):
    try:
        r = requests.get(link, timeout=12)
        soup = BeautifulSoup(r.text, "html.parser")
        h1 = soup.find("h1")
        real_title = h1.text.strip() if h1 else title

        desc_tag = soup.find('meta', {'name': 'description'})
        desc = desc_tag['content'].strip() if desc_tag and desc_tag.get('content') else ""

        img_tag = soup.find('meta', {'property': 'og:image'})
        image = img_tag['content'] if img_tag else None

        # --- Genre ---
        genre = ""
        genre_label = soup.find("span", string=re.compile(r"Genres:", re.I))
        if genre_label:
            genre_span = genre_label.find_next_sibling("span")
            if genre_span:
                inner_genre = genre_span.find("span")
                if inner_genre:
                    genre = inner_genre.get_text(strip=True)
                else:
                    genre = genre_span.get_text(strip=True)

        # --- Trailer ---
        trailer = ""
        video_tag = soup.find("video")
        if video_tag:
            source = video_tag.find("source")
            if source and source.get("src"):
                trailer = source["src"]
        if not trailer:
            iframe = soup.find("iframe", src=re.compile("youtube|vimeo", re.I))
            if iframe and iframe.get("src"):
                trailer = iframe["src"]
        if not trailer:
            trailer_link = soup.find("a", string=re.compile("trailer", re.I))
            if trailer_link and trailer_link.get('href'):
                trailer = trailer_link['href']

        return {
            "title": real_title,
            "description": desc,
            "image": image,
            "trailer": trailer,
            "genre": genre,
            "store_link": link,
        }
    except Exception as e:
        print(f"[VRDB] Error for {title}: {e}")
    return None

def fetch_metadata_from_steam(link, title):
    try:
        r = requests.get(link, timeout=12, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(r.text, "html.parser")
        real_title = soup.find("div", {"class": "apphub_AppName"})
        real_title = real_title.text.strip() if real_title else title
        desc = ""
        desc_tag = soup.find('meta', {'name': 'description'})
        if desc_tag and desc_tag.get('content'):
            desc = desc_tag['content'].strip()
        if not desc:
            desc_div = soup.find("div", {"class": "game_description_snippet"})
            if desc_div:
                desc = desc_div.text.strip()
        img_tag = soup.find('img', {"class": "game_header_image_full"})
        image = img_tag['src'] if img_tag else None

        genre = ""
        details_block = soup.find("div", class_="details_block")
        if details_block:
            genres = details_block.find_all("a", href=re.compile("/genre/"))
            genre = ", ".join([g.text for g in genres]) if genres else ""
            if not genre:
                match = re.search(r"Genre[s]?:\s*(.+)", details_block.text)
                if match:
                    genre = match.group(1).split('\n')[0]

        trailer = ""
        trailer_div = soup.find("div", class_="highlight_movie")
        if trailer_div and trailer_div.find("a", href=re.compile("youtube|steamcdn")):
            trailer = trailer_div.find("a", href=re.compile("youtube|steamcdn"))['href']
        if not trailer:
            iframe = soup.find('iframe', src=re.compile("youtube|vimeo", re.I))
            if iframe:
                trailer = iframe['src']

        return {
            "title": real_title,
            "description": desc,
            "image": image,
            "trailer": trailer,
            "genre": genre,
            "store_link": link,
        }
    except Exception as e:
        print(f"[Steam] Error for {title}: {e}")
    return None

def fetch_metadata_from_itchio(link, title):
    try:
        r = requests.get(link, timeout=12, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(r.text, "html.parser")
        h1 = soup.find("h1", {"class": "game_title"})
        real_title = h1.text.strip() if h1 else title
        desc_tag = soup.find('meta', {'name': 'description'})
        desc = desc_tag['content'].strip() if desc_tag and desc_tag.get('content') else ""
        img_tag = soup.find('meta', {'property': 'og:image'})
        image = img_tag['content'] if img_tag else None

        genre = ""
        genre_span = soup.find("span", class_=re.compile("genre", re.I))
        if genre_span:
            genre = genre_span.get_text(strip=True)
        if not genre:
            for label in soup.find_all(string=re.compile("Genre", re.I)):
                parent = label.parent
                if parent and parent.find_next_sibling():
                    genre = parent.find_next_sibling().get_text(strip=True)
                    break
        if not genre:
            li = soup.find("li", string=re.compile("Genre", re.I))
            if li:
                genre = li.text.split(":", 1)[-1].strip()

        trailer = ""
        iframe = soup.find('iframe', src=re.compile("youtube|vimeo", re.I))
        if iframe:
            trailer = iframe['src']

        return {
            "title": real_title,
            "description": desc,
            "image": image,
            "trailer": trailer,
            "genre": genre,
            "store_link": link,
        }
    except Exception as e:
        print(f"[Itch.io] Error for {title}: {e}")
    return None

def fetch_metadata_from_meta(link, title):
    try:
        r = requests.get(link, timeout=12, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(r.text, "html.parser")
        h1 = soup.find("h1")
        real_title = h1.text.strip() if h1 else title
        desc_tag = soup.find('meta', {'name': 'description'})
        desc = desc_tag['content'].strip() if desc_tag and desc_tag.get('content') else ""
        img_tag = soup.find('meta', {'property': 'og:image'})
        image = img_tag['content'] if img_tag else None

        genre = ""
        for label in soup.find_all(string=re.compile("Genre", re.I)):
            parent = label.parent
            if parent and parent.find_next_sibling():
                genre = parent.find_next_sibling().get_text(strip=True)
                break

        trailer = ""
        iframe = soup.find('iframe', src=re.compile("youtube|vimeo", re.I))
        if iframe:
            trailer = iframe['src']

        return {
            "title": real_title,
            "description": desc,
            "image": image,
            "trailer": trailer,
            "genre": genre,
            "store_link": link,
        }
    except Exception as e:
        print(f"[Meta Quest] Error for {title}: {e}")
    return None

def get_scraper_for_link(url):
    if "uploadvr.com" in url:
        return fetch_metadata_from_uploadvr
    elif "oculusdb" in url:
        return fetch_metadata_from_oculusdb
    elif "vrdb.app" in url:
        return fetch_metadata_from_vrdb
    elif "store.steampowered.com" in url:
        return fetch_metadata_from_steam
    elif "itch.io" in url:
        return fetch_metadata_from_itchio
    elif "meta.com" in url or "oculus.com/experiences" in url:
        return fetch_metadata_from_meta
    else:
        return None

def load_existing_metadata():
    if os.path.exists("games_metadata.json"):
        with open("games_metadata.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_metadata(data):
    with open("games_metadata.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def match_game(existing_titles, cleaned_title):
    for title in existing_titles:
        if cleaned_title.lower() == title.lower():
            return title
    return None

def select_game_folder():
    root = tk.Tk()
    root.withdraw()
    return filedialog.askdirectory(title="Select Your VR Game Folder")

@app.route("/start_update_metadata", methods=["POST"])
def start_update_metadata():
    def background_update():
        existing = load_existing_metadata()
        existing_titles = {item['title']: item for item in existing}
        updated_data = []
        found_titles = set()
        new_games = []
        removed_games = []

        game_folders = os.listdir(GAME_FOLDER)
        progress_data["total"] = len(game_folders)
        progress_data["completed"] = 0

        for folder_name in game_folders:
            cleaned_title = clean_game_title(folder_name)
            found_titles.add(cleaned_title)
            match = match_game(existing_titles, cleaned_title)
            if match:
                item = existing_titles[match]
                item.pop("new", None)
                item.pop("pending_deletion", None)
                updated_data.append(item)
            else:
                meta = {
                    "title": cleaned_title,
                    "description": "",
                    "image": "",
                    "trailer": "",
                    "genre": "",
                    "store_link": "",
                    "new": True
                }
                updated_data.append(meta)
                new_games.append(cleaned_title)
            progress_data["completed"] += 1

        for title, item in existing_titles.items():
            if title not in found_titles:
                item["pending_deletion"] = True
                updated_data.append(item)
                removed_games.append(title)

        save_metadata(updated_data)

        progress_data["summary"] = {
            "new_count": len(new_games),
            "removed_count": len(removed_games),
            "new_titles": new_games
        }

    threading.Thread(target=background_update).start()
    return '', 202

@app.route("/progress_status")
def progress_status():
    return jsonify(progress_data)

@app.route("/games_metadata.json")
def serve_metadata():
    return send_from_directory(".", "games_metadata.json")

@app.route("/confirm_delete_game/<title>", methods=["DELETE"])
def confirm_delete_game(title):
    games = load_existing_metadata()
    games = [g for g in games if g["title"].lower() != title.lower()]
    save_metadata(games)
    return jsonify({"status": "deleted"})

@app.route("/toggle_favorite/<title>", methods=["POST"])
def toggle_favorite(title):
    games = load_existing_metadata()
    updated = False
    for game in games:
        if game["title"].lower() == title.lower():
            game["favorite"] = not game.get("favorite", False)
            updated = True
            break
    if updated:
        save_metadata(games)
        return jsonify({"status": "ok"})
    else:
        return jsonify({"status": "not found"}), 404

@app.route("/set_image/<title>", methods=["POST"])
def set_image(title):
    games = load_existing_metadata()
    data = request.get_json()
    image_url = data.get("image")
    updated = False
    for game in games:
        if game["title"].lower() == title.lower():
            game["image"] = image_url
            updated = True
            break
    if updated:
        save_metadata(games)
        return jsonify({"status": "ok"})
    else:
        return jsonify({"status": "not found"}), 404

@app.route("/fetch_metadata_for_game", methods=["POST"])
def fetch_metadata_for_game():
    data = request.get_json()
    title = data.get("title")
    url = data.get("url")
    if not title or not url:
        return jsonify({"status": "error", "message": "Missing title or url"}), 400
    scraper = get_scraper_for_link(url)
    if not scraper:
        return jsonify({"status": "error", "message": "Unsupported link"}), 400
    meta = scraper(url, title)
    if meta:
        games = load_existing_metadata()
        updated = False
        for game in games:
            if game["title"].lower() == title.lower():
                game.update(meta)
                updated = True
                break
        if not updated:
            meta["title"] = title
            games.append(meta)
        save_metadata(games)
        return jsonify({"status": "ok", "metadata": meta})
    else:
        return jsonify({"status": "error", "message": "Failed to fetch metadata"}), 500

@app.route("/")
def index():
    return render_template_string(open("index.html", encoding="utf-8").read())

def open_browser():
    webbrowser.open("http://127.0.0.1:5000/")

if __name__ == "__main__":
    GAME_FOLDER = select_game_folder()
    threading.Timer(1.5, open_browser).start()
    app.run(debug=True, use_reloader=False)