import csv
from pathlib import Path

MANIFEST_CSV = Path("derived/APCOT2026_public_v13_proceedings_manifest_authors_clean.csv")
NEW_MANIFEST_CSV = Path("derived/APCOT2026_public_v14_proceedings_manifest_authors_clean.csv")

def fix_title_and_authors(row):
    # 0236
    if row['id'] == '0236':
        row['title'] = "Control of Strain Response in Modal-Interference-Based Plastic Optical Fiber Sensors via Double-Side Reactive Ion Etching"
        row['authors'] = "Motoki Kochi, Koyo Shibuta, Keito Ishida, Yuri Wada, Taiki Kumagai, Keita S. Shirai, C.-Y. Lo, H. Lee, Y. Mizuno, D. Yamane"
    # 0201
    elif row['id'] == '0201':
        row['title'] = "Enhanced Suppression of Non-Specific Adsorption of Graphene Oxide-Based Resonant Sensor for Label-Free Virus Sensing"
        row['authors'] = "Viet Khoa Pham, Laoyang Yiayee, Homare Yoshida, Sachiko Sakai, Ippei Akita, Yasuyuki Imaizumi, Tatsuro Goda, I.-H. Kwon, Y.-J. Choi, T. Noda, K. Sawada, K. Takahashi"
    # 0235
    elif row['id'] == '0235':
        row['title'] = "Tri-Layer Soft-Rigid Stretchable Substrates for Direct Fabrication Stretchable Electronics Device"
        row['authors'] = "Shusuke Yamakoshi, Fumika Nakamura, Sho Sato, Yuji Isano, Yutaka Isoda, Ryosuke Matsuda, Naoko Namba, Tsuyoshi Sekitani, Takafumi Uemura, Hiroki Ota"
    # 0426
    elif row['id'] == '0426':
        row['title'] = "Multifunctional Nanostructured Biosensor Platform Integrating Electrical, Optical Transduction Mechanisms"
        row['authors'] = "Hung-Hsiang Wang, Yu-Quan Chen, Chih-Ting Lin"

    # Subscripts
    subs = {
        '0218': ('Ti3C2Tx', 'Ti₃C₂Tₓ'),
        '0188': ('BaTiO3', 'BaTiO₃'),
        '0278': ('MoS2', 'MoS₂'),
        '0192': ('0.4Pb(Mg1/3Nb2/3)O3–0.22PbZrO3-0.38PbTiO3', '0.4Pb(Mg₁/₃Nb₂/₃)O₃–0.22PbZrO₃-0.38PbTiO₃'),
        '0320': ('WS2/Ga2O3', 'WS₂/Ga₂O₃'),
        '0341': [('Al2O3', 'Al₂O₃'), ('SnO2', 'SnO₂')],
        '0303': ('TiO2', 'TiO₂'),
        '0346': ('Al2O3', 'Al₂O₃'),
        '0354': ('Ta2O5', 'Ta₂O₅'),
        '0328': ('Fe3O4', 'Fe₃O₄'),
    }
    
    if row['id'] in subs:
        replacements = subs[row['id']]
        if isinstance(replacements, tuple):
            replacements = [replacements]
        for old, new in replacements:
            row['title'] = row['title'].replace(old, new)
            
    # Subscript checking - ensure they are correct
    # (they already use unicode subscripts, but we just re-assign to be safe if they didn't)
    # the existing ones like SiO2 are already SiO₂ in CSV.

    # Author formatting
    if row['id'] == '0447':
        row['authors'] = "Fuyang Qu, Luoquan Li, Juan Li, Guangyao Cheng, Yi-Ping Ho"
    elif row['id'] == '0430':
        row['authors'] = "Guangyao Cheng, Luoquan Li, Weilun Liu, Silin Zhong, Yi-Ping Ho"
    elif row['id'] == '0454':
        row['authors'] = "Yi-Hsien Wu, Ching-Kai Lin, Chen-Wei Chang, Chin-Chung Chen, Shu-Chung Lee, Yun-Chien Cheng, Tien-Kan Chung"
    elif row['id'] == '0253':
        row['authors'] = "Qinru Xiao, Guangyao Cheng, Kuan Wen Lou, Yi-Ping Ho"
    elif row['id'] == '0416':
        row['authors'] = "Yi-Jing Liao, Shu-Ping Lin"

    return row

def day_to_int(day_str):
    if "Monday" in day_str: return 1
    if "Tuesday" in day_str: return 2
    if "Wednesday" in day_str: return 3
    return 4

def main():
    rows = []
    with open(MANIFEST_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        for row in reader:
            row = fix_title_and_authors(row)
            rows.append(row)

    # Reorder the rows!
    # Primary sort: day
    # Secondary sort: session_time
    # Tertiary sort: session_label
    # Quaternary sort: time
    # This will alphabetize the sessions (A, B, C, D, E) within the time block!
    def sort_key(r):
        return (day_to_int(r['day']), r['session_time'], r['session_label'], r['time'])

    rows.sort(key=sort_key)

    with open(NEW_MANIFEST_CSV, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Written to {NEW_MANIFEST_CSV}")

if __name__ == '__main__':
    main()
