"""Quick check: which target ports now have analysis_version=4 briefings?"""
import google.cloud.firestore as gfs

db = gfs.Client(project='traveltime-465606')
briefings = list(db.collection('daily_briefings').stream())

ports = [
    'Port of Beira, Mozambique',
    'Port of Balboa, Panama',
    'Port of Cristobal, Panama',
    'Port of Jebel Ali, Dubai',
    'Port of Salalah, Oman',
    'Port of Casablanca, Morocco',
    'Port of Melbourne, Australia',
    'Port Botany, Sydney, Australia',
    'Port of Brisbane, Australia',
    'Port of Fremantle, Australia',
    'Port of Adelaide, Australia',
]

for port in ports:
    matches = [d for d in briefings if d.to_dict().get('location_context','').startswith(port)]
    versions = [str(d.to_dict().get('analysis_version','?')) for d in matches]
    status = "✅ REGENERATED" if all(v == '4' for v in versions) and versions else ("NO DATA" if not versions else "⚠ MIXED")
    print(f'{status:20s}  {port}: {len(matches)} briefings (v{", v".join(versions) if versions else "none"})')
