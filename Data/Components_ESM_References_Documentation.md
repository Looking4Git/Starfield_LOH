# Dokumentation der Tabelle `Components_ESM_References` (Creation Engine 2)

Diese Datei beschreibt den Aufbau und die Bedeutung der Spalten in der Tabelle `Components_ESM_References` für die Klassifizierung von Starfield-Modifikationen im Rahmen von **Starfield LOH**.

---

## 1. Übergreifende Spalten

*   **Component_ID**: Fremdschlüssel auf `Components.ID`. Identifiziert die zugehörige Master- oder Mod-Datei (`.esm` / `.esp`).

---

## 2. Gravity 1: System & Quests (System- und Queststeuerungen)

*   **GMST / GMST_Override**: *Game Setting*. Systemkonfigurationen (z. B. Gravitationsstärke, KI-Verhalten, Gameplay-Grenzwerte). `Override` zeigt an, dass ein Vanilla-Wert modifiziert wurde.
*   **QUST / QUST_Override**: *Quest*. Quest-Steuerungsdatensätze.
*   **QUST_FULL**: Quests, die einen Anzeigenamen (`FULL`-Subrecord) besitzen (indiziert eine echte, für den Spieler sichtbare Quest im Logbuch).
*   **QUST_INDX**: Quest-Indizes (Stages/Ziele).
*   **QUST_QOBJ**: Quest-Objectives (Teilaufgaben).
*   **QUST_QTYP_0 bis QUST_QTYP_5**: Zähler für Quest-Kategorien (0: Undefiniert, 1: Main Quest, 2: Faction Quest, 3: Side Quest, 4: Radiant Quest, 5: Misc/Sonstiges).
*   **Shifter_Quest_Starter / Trader / Chest / Ship**: Berechnete Koeffizienten (0.0 bis 1.0), die beschreiben, wie eine Quest ins Spiel injiziert wird (z. B. über Händler, Truhen oder Terminals).
*   **DIAL / DIAL_Override**: *Dialogue Branch*. Dialogthemen und -zweige.
*   **INFO / INFO_Override**: *Dialogue Info*. Einzelne gesprochene Sätze und Reaktionen innerhalb von Dialogen.
*   **GLOB / GLOB_Override**: *Global Variable*. Globale Variablen zur Systemkonfiguration oder Tweak-Steuerung.

---

## 3. Gravity 2: World & Structure (Weltplatzierungen und Strukturen)

*   **WRLD**: *Worldspace*. Ganze Planetenoberflächen oder große Außenbereiche.
*   **CELL / CELL_Override**: *Cell*. Einzelne Planetenquadrate (Außenbereiche) oder Ladezonen (Innenräume).
*   **NVNM / NAVM**: *NavMesh*. Navigationspfade für Begleiter und NPCs. Zeigt an, dass die Wegfindung modifiziert oder neu angelegt wurde.
*   **REFR**: *Placed Object Reference*. Konkrete Platzierung eines Objekts in einer Zelle (z. B. eine Kiste, ein Tisch, ein NPC).
*   **STAT / STAT_Override**: *Static*. Unbewegliche 3D-Modelle (Häuser, Felsen, Wände, Deko-Objekte).
*   **FURN / FURN_Override**: *Furniture*. Möbel und interaktive Stationsplatzierungen (Stühle, Betten, Werkbänke).
    *   **FURN_VMRT** (*Vehicle Mount*): Plätze für Fahrzeuginsassen (Sitze).
    *   **FURN_VCMT** (*Vehicle Camera*): Kameraperspektiven an Fahrzeugen.
    *   **FURN_VWWD** (*Vehicle Wheels*): Radaufhängungen und Radplatzierungen für Landfahrzeuge.
    *   **FURN_VCTT** (*Vehicle Controls*): Cockpit-Steuerungen für Fahrzeuge.
*   **TERM**: *Terminal*. Interaktive Computerterminals.
*   **LCTN / LCTN_Override**: *Location*. Definitionen von Orten, Städten, Dungeons oder Points of Interest (POI).
*   **FLOR / FLOR_Override**: *Flora*. Pflanzen-Definitionen, erntebare organische Ressourcen und Gewächshaus-Erzeugnisse.
*   **TREE / TREE_Override**: *Tree*. Baum-Definitionen, größere Landschafts- und Waldvegetationsobjekte.

---

## 4. Gravity 3: Gameplay & Actors (Charaktere, Werte und Gameplay-Logik)

*   **NPC_ / NPC__Override**: *Non-Player Character / Actor*. Charakter-Definitionen (Gegner, Begleiter, Händler, Kreaturen).
*   **ACHR**: *Actor Reference*. Platzierte Instanz eines NPCs in der Spielwelt.
*   **PKIN**: *Pack-In*. Vorgefertigte Gruppen von Objekten, die zusammen in die Welt geladen werden (oft für POIs / Außenposten).
*   **PERK / PERK_Override**: *Perk*. Fertigkeiten, Skills und passive Eigenschaften.
*   **AVIF / AVIF_Override**: *Actor Value Information*. Attribute, Fraktionsbeziehungen und Statuswerte (z. B. Gesundheit, Tragekapazität).
*   **MOVT**: *Movement Type*. Bewegungseigenschaften (Geschwindigkeit, Beschleunigung für Gehen, Laufen, Fliegen).
*   **NPC_KYWD_Ship / Companion / Creature / Shop**: Kategorisierte Zählung von NPCs basierend auf ihren internen Editor-IDs (z. B. Händler, Begleiter, Monster, Schiffstechniker).
*   **RACE / RACE_Override**: *Race*. Definitionen von spielbaren und nicht-spielbaren Rassen, Kreaturen-Skeletten oder Eigenschaften.

---

## 5. Gravity 4: Visuals, Audio & Interface (Effekte, Sounds, Grafiken)

*   **TXST**: *Texture Set*. Texturdefinitionen für 3D-Modelle.
*   **MATO**: *Material Object*. Shader- und Materialeigenschaften.
*   **MSWP / MSWP_Override**: *Material Swap*. Austausch-Tabellen für Materialien und Texturen (wird in Starfield für Skins an Waffen, Rüstungen und Schiffen verwendet).
*   **LMSW / LMSW_Override**: *Leveled Material Swap*. Dynamische Material- und Textur-Austauschlisten basierend auf Spielerlevel oder anderen Bedingungen.
*   **LIGH / LIGH_Override**: *Light*. Lichtquellen (Lampen, Scheinwerfer, Raumbeleuchtungen).
    *   **LIGH_FNAM** (*Light Projection*): Lichtquellen, die eine gerichtete Projektionstextur (`TXST`) besitzen (z. B. Spotlights oder Scheinwerfer).
*   **SNDR / SNDR_Override**: *Sound Descriptor*. Sound-Einstellungen (Lautstärke, Hall, Reichweite).
*   **SOUN**: *Sound*. Verweise auf Audio-Dateien.
*   **MUSC / MUSC_Override**: *Music Type*. Musik-Wiedergabelisten und -Zuweisungen (z. B. Kampfmusik, Hintergrundmusik für Planeten/Zellen).
*   **CLFM**: *Color Form*. Farbpaletten für Kleidung, Haare oder Benutzeroberflächen.
*   **HDPT**: *Head Part*. Gesichtsmerkmale für den Charaktereditor (Haare, Bärte, Augen).
*   **MGEF / MGEF_Override**: *Magic Effect*. Magische Effekte (Heilung, Statuseffekte, Buffs, Debuffs).
*   **EFSH / EFSH_Override**: *Effect Shader*. Visuelle Grafikeffekte auf Objekten/NPCs (z. B. Brennen, Schildeffekte).
*   **SPEL / SPEL_Override**: *Spell*. Zauber, Fähigkeiten und Krankheiten.
*   **ENCH / ENCH_Override**: *Enchantment*. Verzauberungen und Waffen-/Rüstungseffekte.
*   **VFXS / VFXS_Override**: *Visual Effect*. Partikeleffekte (Rauch, Funken, Explosionen).
*   **ALCH / ALCH_Override**: *Alchemy*. Chemikalien, Nahrungsmittel, Medizin und Tränke.

---

## 6. Gravity 5: Items, Ships & Vehicles (Waffen, Ausrüstung, Schiffe, Fahrzeuge)

*   **WEAP / WEAP_Override**: *Weapon*. Waffen aller Art (Handfeuerwaffen, Granaten, Minen, Fahrzeugwaffen, Schiffswaffen).
    *   **WEAP_KWDA_Vehicle**: Zähler für Waffen, die Keywords oder Editor-IDs besitzen, welche sie eindeutig als **Fahrzeugwaffen** identifizieren (z. B. Keywords wie `VehicleWeaponControllerFeedback` oder EDID-Teilstrings wie `rev8`, `moonjumper`, `deimog`, `hybrid`). Wird zur Bereinigung von echten Handfeuerwaffen genutzt.
    *   **WEAP_KWDA_Ship**: Zähler für Waffen, die als **Schiffswaffen** identifiziert wurden (z. B. über Schiffswaffen-Keywords oder EDID-Begriffe wie `spaceship` / `ship_weapon` etc.).
    *   **WEAP_KWDA_Helper**: Zähler für Waffen, die rein als **Hilfswerkzeuge/Steuerungen** dienen (z. B. Fernbedienungen für Laderampen, Triebwerksaktivatoren, Drohnendetotatoren, Dummy-Projektile). Erkennung über EDID-Teilstrings wie `remote`, `detonator`, `activator`, `controller`, `control`, `dummy`, `tuner` oder das Vanilla-Keyword `0x249fb6` (`AttachableEmbeddedWeaponKeyword`).
*   **AMMO / AMMO_Override**: *Ammunition*. Munition für Schusswaffen.
*   **ARMO / ARMO_Override**: *Armor*. Raumanzüge, Helme, Rucksäcke und normale Kleidung.
*   **APWR**: *Armor Addon / Wearable Modifier*. Rüstungsteile und Modifikations-Slots für Kleidung.
*   **OMOD / OMOD_Override**: *Object Modification*. Modifikationen für Waffen und Rüstungen (wird in Starfield auch zur Anwendung von Skins verwendet).
*   **COBJ / COBJ_Override**: *Constructible Object*. Handwerksrezepte für Werkbänke und das Außenposten-Bausystem.
*   **SPAC / SPAC_Override**: *Spaceship*. Raumschiffe und deren Kern-Layouts.
*   **SHST / SHST_Override**: *Ship Structure*. Bauteile und Triebwerksparameter von Schiffen.
*   **SMOD / SMOD_Override**: *Ship Module*. Waffen, Schilde, Antriebe und Reaktoren für Raumschiffe.
*   **GBFM**: *Gameplay Blueprint*. Allgemeine Gameplay-Blaupausen (wird in Starfield für Schiffskomponenten, Landfahrzeug-Zuweisungen und NPC-Spawnzonen/Crowd-Regionen verwendet).
*   **GBFM_EDID_CrowdRegion**: Zähler für Gameplay-Blaupausen (`GBFM`), die anhand ihrer Editor-ID (`EDID`) eindeutig als städtische NPC-Spawnzonen (Crowd-Regionen) identifiziert wurden. Dient zur Bereinigung der echten Schiffskonfigurationen in der Ausschlussmatrix.
*   **GBFM_EDID_Vehicle**: Zähler für Gameplay-Blaupausen (`GBFM`), die anhand ihrer Editor-ID (`EDID`) als Landfahrzeug-Designs/Steuerungen identifiziert wurden. Dient ebenfalls zur Bereinigung der echten Schiffskonfigurationen in der Ausschlussmatrix.
*   **STMP**: *Ship Template*. Schablonen/Vorlagen für Raumschiffe.
*   **STND**: *Ship Node*. Anschlusspunkte (Snap-Nodes) für Schiffsteile.
*   **STBH**: *Ship Behavior*. Verhaltensdefinitionen für Schiffsteile (z. B. begehbare Luken, Türen und Wände in Habs).
*   **STDT**: *Star*. Daten und Eigenschaften für Sonnen/Sterne (z. B. Sternenfarben, Helligkeit). Has nothing to do with ships (ship data).
*   **VEHI / VEHI_Override**: *Vehicle*. Landfahrzeuge (z. B. der REV-8 oder Moonjumper).
*   **VMOD / VMOD_Override**: *Vehicle Module*. Modifikationen und Ausbaustufen für Landfahrzeuge.
*   **RSPJ**: *Space Project*. Definition von Sternensystemen und Galaxien-Projektionen.
*   **KYWD**: *Keyword*. Labels und Kategorisierungsschlüssel der Creation Engine.
*   **PKEY**: *Property Key*. Eigenschaftsschlüssel für Skripte.
*   **LVLI / LVLI_Override**: *Leveled Item*. Dynamische Item-Loot-Tabellen.
*   **LVLN / LVLN_Override**: *Leveled NPC*. Dynamische NPC-Spawn-Tabellen.
*   **LVLP / LVLP_Override**: *Leveled Pack-In*. Dynamische Pack-In Platzierungstabellen.
*   **FLST / FLST_Override**: *FormID List*. Sammellisten von FormIDs (z. B. für Rezepte, Händlerlisten oder Outfits).
*   **MISC / MISC_Override**: *Misc Object*. Sonstige Objekte, Ressourcen, Trays (Tabletts), Schneekugeln und Schrott.
*   **KEYM / KEYM_Override**: *Key*. Schlüssel und Schlüsselkarten für Schlösser und Türen.
*   **BOOK / BOOK_Override**: *Book*. Bücher, Notizen, Slates und Datenpads.

---

## 7. Spezifische Bereinigungsspalten (Lösch- und Deinstallations-Flags)

*   **REFR_Deleted / REFR_Disabled / REFR_Buried**: Zähler für Modifikationen, die Objekte aus der Spielwelt entfernen (gelöscht, deaktiviert oder unter die Erde vergraben).
*   **SPEL_Remove / MGEF_Remove / EFSH_Remove / ENCH_Remove / VFXS_Remove / ALCH_Remove / PERK_Remove / FLOR_Remove / TREE_Remove**: Instanzen, bei denen bestehende Statuseffekte, Effekte, Rüstungseigenschaften, Partikeleffekte, Rezepte/Tränke, Perks, Pflanzen oder Bäume gezielt über eine Modifikation aus dem Spielsystem deinstalliert/entfernt werden.
