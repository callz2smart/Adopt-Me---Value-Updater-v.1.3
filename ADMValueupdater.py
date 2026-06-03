import requests
import re
import json
import time
from decimal import Decimal, ROUND_HALF_UP

_pet_index = None

def _fetch_pets():
    global _pet_index
    if _pet_index is not None:
        return

    url = "https://elvebredd.com/adopt-me-calculator"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    response = requests.get(url, headers=headers)
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.+?)"\]\)', response.text)

    for chunk in chunks:
        if "initialPets" not in chunk:
            continue
        decoded = chunk.encode().decode("unicode_escape")
        idx = decoded.find('"initialPets":')
        if idx == -1:
            continue
        arr_start = decoded.index("[", idx)
        depth = 0
        for i in range(arr_start, len(decoded)):
            if decoded[i] == "[":
                depth += 1
            elif decoded[i] == "]":
                depth -= 1
                if depth == 0:
                    pets = json.loads(decoded[arr_start:i + 1])
                    _pet_index = {}
                    for p in pets:
                        name = p.get("name")
                        if name:
                            _pet_index[name.lower()] = p
                    return
    raise RuntimeError("Could not find pet data on the page.")

def normalize_value(value):
    if value is None:
        return None
    
    if isinstance(value, (int, float)):
        str_value = str(value)
        
        if '.' in str_value and len(str_value.split('.')[1]) > 3:
            decimal_value = Decimal(str(value))
            if 0 < value < 1:
                normalized = float(decimal_value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
                return normalized
            elif value >= 1:
                normalized = int(round(value))
                return normalized
        
        if abs(value - round(value)) < 0.001:
            return int(round(value))
        
        if isinstance(value, float):
            return round(value, 2)
        
        return value
    
    return value

def convert_to_full_words(item_name):
    words = item_name.split()
    
    mega = False
    neon = False
    fly = False
    ride = False
    
    remaining_words = []
    i = 0
    while i < len(words):
        word = words[i].upper()
        
        if len(word) <= 4 and all(c in 'MNRF' for c in word):
            for char in word:
                if char == 'M':
                    mega = True
                elif char == 'N':
                    neon = True
                elif char == 'F':
                    fly = True
                elif char == 'R':
                    ride = True
            i += 1
        else:
            word_lower = words[i].lower()
            if word_lower == 'mega':
                mega = True
                i += 1
            elif word_lower == 'neon':
                neon = True
                i += 1
            elif word_lower == 'fly':
                fly = True
                i += 1
            elif word_lower == 'ride':
                ride = True
                i += 1
            else:
                remaining_words.append(words[i])
                i += 1
    
    pet_name = ' '.join(remaining_words)
    
    search_words = []
    
    if mega and neon:
        search_words.append("Mega Neon")
    elif mega:
        search_words.append("Mega")
    elif neon:
        search_words.append("Neon")
    
    if fly and ride:
        search_words.append("Fly Ride")
    elif fly:
        search_words.append("Fly")
    elif ride:
        search_words.append("Ride")
    
    search_words.append(pet_name)
    
    full_query = ' '.join(search_words)
    
    return {
        'full_query': full_query,
        'pet_name': pet_name,
        'mega': mega,
        'neon': neon,
        'fly': fly,
        'ride': ride
    }

def get_value_for_item(item_name):
    _fetch_pets()
    
    parsed = convert_to_full_words(item_name)
    full_query = parsed['full_query']
    pet_name = parsed['pet_name']
    
    if not pet_name:
        return None
    
    if parsed['mega'] and parsed['neon']:
        tier = "m"
    elif parsed['neon']:
        tier = "n"
    else:
        tier = "r"
    
    if parsed['fly'] and parsed['ride']:
        modifier = "fly&ride"
    elif parsed['fly']:
        modifier = "fly"
    elif parsed['ride']:
        modifier = "ride"
    else:
        modifier = "nopotion"
    
    tier_prefix = {"r": "rvalue", "n": "nvalue", "m": "mvalue"}[tier]
    key = f"{tier_prefix} - {modifier}"
    
    pet_data = _pet_index.get(pet_name.lower())
    
    if pet_data is None:
        pet_name_clean = re.sub(r'\s*(?:pet|egg|stroller|vehicle|toy|gift|plush|rattle|balloon|grapple|pogo|propeller|disc|frisbee|throwing|food|drink)$', '', pet_name).strip().lower()
        pet_data = _pet_index.get(pet_name_clean)
    
    if pet_data is None:
        return None
    
    for k in [key, tier_prefix, "value"]:
        v = pet_data.get(k)
        if v is not None and v != "?" and v != "":
            if isinstance(v, str) and "-" in v:
                parts = v.split("-")
                try:
                    left = float(parts[0])
                    right = float(parts[1])
                    avg = (left + right) / 2
                    normalized = normalize_value(avg)
                    return normalized
                except:
                    return v
            
            if isinstance(v, (int, float)):
                return normalize_value(v)
            
            if isinstance(v, str):
                try:
                    num = float(v.replace(',', ''))
                    return normalize_value(num)
                except:
                    return v
            
            return v
    
    return pet_data.get("value")

def update_adm_values():
    print("="*60)
    print("FETCHING ADM VALUES FROM ELVEBREDD")
    print("="*60)
    print()
    
    print("Fetching latest values from Elvebredd...")
    try:
        _fetch_pets()
        print("Successfully fetched pet data!\n")
    except Exception as e:
        print(f"Failed to fetch pet data: {e}")
        return
    
    with open('mm2.json', 'r') as f:
        items = json.load(f)
    
    updated_count = 0
    failed_items = []
    skipped_count = 0
    
    print("Updating ADM items (keeping 1-letter prefixes)...\n")
    print(f"{'Item Name':<30} {'Old Value':>12} {'New Value':>12} {'Status':>10}")
    print("-" * 70)
    
    for item_name, item_data in items.items():
        if item_data.get('type') != 'ADM':
            skipped_count += 1
            continue
        
        try:
            new_value = get_value_for_item(item_name)
            
            if new_value is not None:
                old_value = item_data.get('value', 0)
                
                old_normalized = normalize_value(old_value)
                new_normalized = normalize_value(new_value)
                
                if old_normalized != new_normalized:
                    item_data['value'] = new_value
                    updated_count += 1
                    
                    old_display = f"{old_normalized:,}" if isinstance(old_normalized, int) else f"{old_normalized:,.2f}"
                    new_display = f"{new_normalized:,}" if isinstance(new_normalized, int) else f"{new_normalized:,.2f}"
                    
                    print(f"{item_name:<30} {old_display:>12} {new_display:>12} {'UPDATED':>10}")
                else:
                    old_display = f"{old_normalized:,}" if isinstance(old_normalized, int) else f"{old_normalized:,.2f}"
                    new_display = f"{new_normalized:,}" if isinstance(new_normalized, int) else f"{new_normalized:,.2f}"
                    
                    print(f"{item_name:<30} {old_display:>12} {new_display:>12} {'SAME':>10}")
            else:
                failed_items.append(item_name)
                print(f"{item_name:<30} {'N/A':>12} {'N/A':>12} {'NOT FOUND':>10}")
                
        except Exception as e:
            failed_items.append(item_name)
            print(f"{item_name:<30} {'ERROR':>12} {'ERROR':>12} {'FAILED':>10}")
        
        time.sleep(0.1)
    
    with open('mm2.json', 'w') as f:
        json.dump(items, f, indent=2)
    
    print("\n" + "="*60)
    print("UPDATE COMPLETE!")
    print("="*60)
    print(f"Updated: {updated_count} ADM items")
    print(f"Skipped: {skipped_count} non-ADM items")
    print(f"Failed: {len(failed_items)} items")
    
    if failed_items:
        print("\nFailed items (not found on Elvebredd):")
        for item in failed_items[:20]:
            print(f"  - {item}")
        if len(failed_items) > 20:
            print(f"  - ...and {len(failed_items) - 20} more")

def test_conversion():
    test_items = [
        "MFR Hedgehog",
        "NFR Hedgehog",
        "FR Hedgehog",
        "R Hedgehog",
        "F Hedgehog",
        "M Hedgehog",
        "MF Hedgehog",
        "MR Hedgehog",
        "MFR Crow",
        "Shadow Dragon",
        "Bat Dragon",
        "NR Turtle",
        "NF Turtle",
        "M Neon Shadow Dragon"
    ]
    
    print("Testing conversion (1-letter -> full words for search):")
    print("-" * 70)
    print(f"{'Original (JSON)':<25} {'Search Query':<35} {'Found?':<10}")
    print("-" * 70)
    
    _fetch_pets()
    
    for item in test_items:
        parsed = convert_to_full_words(item)
        value = get_value_for_item(item)
        found = "YES" if value else "NO"
        print(f"{item:<25} {parsed['full_query']:<35} {found:<10}")
        
        if value:
            normalized = normalize_value(value)
            if isinstance(normalized, int):
                print(f"{'':<25} {'':<35} Value: {normalized:,}")
            else:
                print(f"{'':<25} {'':<35} Value: {normalized:.2f}")
        print()

if __name__ == "__main__":
    print("\n" + "="*60)
    print("ADM VALUE UPDATER")
    print("="*60)
    print("\nOptions:")
    print("1. Test conversion (see how 1-letter prefixes are interpreted)")
    print("2. Update ADM values (keeps 1-letter prefixes in JSON)")
    print()
    
    choice = input("Enter choice (1 or 2): ").strip()
    
    if choice == "1":
        test_conversion()
    elif choice == "2":
        update_adm_values()
    else:
        print("Invalid choice! Running update...")
        update_adm_values()
