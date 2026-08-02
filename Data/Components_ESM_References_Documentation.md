# Dokumentation der Tabelle `Components_ESM_References` (Creation Engine 2)

Diese Datei beschreibt den Aufbau und die Bedeutung der Spalten in der Tabelle `Components_ESM_References` für die Klassifizierung von Starfield-Modifikationen im Rahmen von **Starfield LOH**.

> [!NOTE]
> **Allgemeine Leseart des Datenmodells:**
> *   **Stamm-Zähler** (z. B. `CELL`, `STAT`, `WEAP`, `LIGH`): Die **Gesamtzahl** aller Einträge dieses Typs in der Mod-Datei (Neu + Überschrieben).
> *   **Suffix `_Override`** (z. B. `CELL_Override`, `STAT_Override`, `WEAP_Override`): Der **Teilbereich** der Gesamtzahl, der bestehende Einträge aus Masterfiles überschreibt.
> *   **Echte neue Einträge** ergeben sich folglich immer durch die Subtraktion: `Stamm-Zähler - Suffix_Override`.

---

## 1. Übergreifende Spalten

*   **Component_ID**: Fremdschlüssel auf `Components.ID`. Identifiziert die zugehörige Master- oder Mod-Datei (`.esm` / `.esp`).

---

## 2. Zählerspalten (Alphabetisch sortiert nach Stamm-Name und Suffix)

*   **ACHR**: *Actor Reference*. Platzierte Instanz eines NPCs in der Spielwelt.
*   **ALCH / ALCH_Override / ALCH_Remove**: *Alchemy*. Chemikalien, Nahrungsmittel, Medizin und Tränke. `Remove` markiert deinstallierte/entfernte Rezepte.
*   **AMMO / AMMO_Override**: *Ammunition*. Munition für Schusswaffen.
*   **APWR**: *Armor Addon / Wearable Modifier*. Rüstungsteile und Modifikations-Slots für Kleidung.
*   **ARMO / ARMO_Override**: *Armor*. Raumanzüge, Helme, Rucksäcke und normale Kleidung.
*   **AVIF / AVIF_Override**: *Actor Value Information*. Attribute, Fraktionsbeziehungen und Statuswerte (z. B. Gesundheit, Tragekapazität).
*   **BOOK / BOOK_Override**: *Book*. Bücher, Notizen, Slates und Datenpads.
*   **BIOM / BIOM_Override**: *Biome*. Biom-Definitionsdatensätze. Bestimmen die Verteilung von Flora, Fauna, Texturen und Landschafts-Features.
*   **CELL / CELL_Dummy / CELL_Override / CELL_Override_Dummy / CELL_Override_PackIn / CELL_PackIn**: *Cell*. Einzelne Planetenquadrate (Außenbereiche) oder Ladezonen (Innenräume). 
    *   `CELL_Dummy` / `CELL_Override_Dummy`: Erfasst reine Skript-, Holding-, Test- und Utility-Zellen ohne Location oder Ingame-Namen.
    *   `CELL_PackIn` / `CELL_Override_PackIn`: Erfasst Zell-Schablonen für Fertigbauteile (PackIns).
*   **CLFM**: *Color Form*. Farbpaletten für Kleidung, Haare oder Benutzeroberflächen.
*   **CLMT / CLMT_Override**: *Climate*. Klimazyklen (Tag-Nacht-Rhythmen, Wetterverteilungen für Planeten).
*   **COBJ / COBJ_Override / COBJ_BNAM_Outpost_Heavy / COBJ_BNAM_Outpost_Soft / COBJ_BNAM_Ship**: *Constructible Object*. Handwerksrezepte für Werkbänke und das Außenposten- oder Schiffbausystem.
    *   `COBJ_BNAM_Outpost_Heavy`: Rezepte für Außenposten-Kernkomponenten (Extraktoren, Generatoren, Abwehr).
    *   `COBJ_BNAM_Outpost_Soft`: Rezepte für Außenposten-Strukturen und -Deko (Habs, Kisten, Roboter).
    *   `COBJ_BNAM_Ship`: Rezepte für den Schiffsbau-Editor (Workbench-Abgleich).
*   **CONT / CONT_Override**: *Container*. Behälter und Kisten.
*   **DIAL / DIAL_Override**: *Dialogue Branch*. Dialogthemen und -zweige.
*   **EFSH / EFSH_Override / EFSH_Remove**: *Effect Shader*. Visuelle Grafikeffekte auf Objekten/NPCs.
*   **ENCH / ENCH_Override / ENCH_Remove**: *Enchantment*. Verzauberungen und Rüstungs-/Waffeneffekte.
*   **FLOR / FLOR_Override / FLOR_Remove**: *Flora*. Pflanzen-Definitionen und organische Ressourcen.
*   **FLST / FLST_Override**: *FormID List*. Sammellisten von FormIDs (z. B. für Händler oder Rezepte).
*   **FURN / FURN_Override / FURN_VCMT / FURN_VCTT / FURN_VMRT / FURN_VWWD**: *Furniture*. Möbel und interaktive Stationsplatzierungen.
    *   `FURN_VMRT` (*Vehicle Mount*): Plätze für Fahrzeuginsassen (Sitze).
    *   `FURN_VCMT` (*Vehicle Camera*): Kameraperspektiven an Fahrzeugen.
    *   `FURN_VWWD` (*Vehicle Wheels*): Radaufhängungen für Landfahrzeuge.
    *   `FURN_VCTT` (*Vehicle Controls*): Cockpit-Steuerungen für Fahrzeuge.
*   **GBFM / GBFM_EDID_CrowdRegion / GBFM_EDID_Vehicle**: *Gameplay Blueprint*. Allgemeine Gameplay-Blaupausen.
    *   `GBFM_EDID_CrowdRegion`: NPC-Spawnzonen (Crowds) in Städten.
    *   `GBFM_EDID_Vehicle`: Landfahrzeug-Blaupausen.
*   **GLOB / GLOB_Override**: *Global Variable*. Globale Variablen zur Systemkonfiguration oder Tweak-Steuerung.
*   **GMST / GMST_Override**: *Game Setting*. Systemkonfigurationen (z. B. Gravitationsstärke, Gameplay-Grenzwerte).
*   **HDPT**: *Head Part*. Gesichtsmerkmale für den Charaktereditor.
*   **IMAD / IMAD_Override**: *Image Space Modifier*. Post-Processing-Shader und Farbkorrekturen für Wetter und Effekte.
*   **INFO / INFO_Override**: *Dialogue Info*. Einzelne gesprochene Sätze und Reaktionen.
*   **INNR / INNR_Override**: *Instance Naming Rules*. Namensregeln zur dynamischen Namensvergabe von Gegenständen wie Waffen und Rüstungen.
*   **KEYM / KEYM_Override**: *Key*. Schlüssel und Schlüsselkarten für Schlösser und Türen.
*   **LAND / LAND_Override**: *Landscape*. Landschafts-Höhendaten und 3D-Verformungen des Bodens.
*   **KYWD**: *Keyword*. Labels und Kategorisierungsschlüssel der Creation Engine.
*   **LCTN / LCTN_Override / LCTN_KYWD_City / LCTN_KYWD_Dungeon / LCTN_KYWD_Playerhome / LCTN_KYWD_Settlement**: *Location*. Definitionen von Orten, Städten, Dungeons oder Points of Interest (POI).
*   **LIGH / LIGH_Override / LIGH_FNAM**: *Light*. Lichtquellen. `LIGH_FNAM` erfasst projizierende Lichtquellen (Spotlights).
*   **LMSW / LMSW_Override**: *Leveled Material Swap*. Dynamische Material- und Textur-Austauschlisten basierend auf Spielerlevel.
*   **LVLI / LVLI_Override**: *Leveled Item*. Dynamische Item-Loot-Tabellen.
*   **LVLN / LVLN_Override**: *Leveled NPC*. Dynamische NPC-Spawn-Tabellen.
*   **LVLP / LVLP_Override**: *Leveled Pack-In*. Dynamische Pack-In Platzierungstabellen.
*   **MATO**: *Material Object*. Shader- und Materialeigenschaften.
*   **MGEF / MGEF_Override / MGEF_Remove**: *Magic Effect*. Magische Effekte (Heilung, Buffs, Debuffs).
*   **MISC / MISC_Override**: *Misc Object*. Sonstige Objekte, Ressourcen, Trays (Tabletts), Schneekugeln und Schrott.
*   **MOVT**: *Movement Type*. Bewegungseigenschaften (Geschwindigkeit, Beschleunigung).
*   **MSTT / MSTT_Override**: *Movable Static*. Bewegliche statische Objekte (z. B. Becher, physikalisch bewegliche Dekorationsgegenstände).
*   **MSWP / MSWP_Override**: *Material Swap*. Austausch-Tabellen für Materialien und Texturen (Waffen/Rüstungs-Skins).
*   **MUSC / MUSC_Override**: *Music Type*. Musik-Wiedergabelisten und -Zuweisungen.
*   **NAVM**: *NavMesh*. Navigationspfade für Begleiter und NPCs.
*   **NPC_ / NPC__Override / NPC_KYWD_Companion / NPC_KYWD_Creature / NPC_KYWD_Ship / NPC_KYWD_Shop**: *Non-Player Character / Actor*. Charakter-Definitionen (Gegner, Begleiter, Händler, Kreaturen).
*   **NVNM**: *NavMesh*. Navigationspfade (alternative Darstellung).
*   **OMOD / OMOD_Override**: *Object Modification*. Modifikationen für Waffen und Rüstungen.
*   **PCBN**: *Planet Content Block Node*. Knotenpunkte zur prozeduralen Verteilung von POIs.
*   **PCCN**: *Planet Content Connection*. Verknüpfungen zur Einspeisung von Custom-POIs in das Spawnsystem.
*   **PERK / PERK_Override / PERK_Remove**: *Perk*. Fertigkeiten, Skills und passive Eigenschaften.
*   **PKEY**: *Property Key*. Eigenschaftsschlüssel für Skripte.
*   **PKIN**: *Pack-In*. Vorgefertigte Gruppen von Objekten, die zusammen in die Welt geladen werden.
*   **QUST / QUST_Override / QUST_FULL / QUST_INDX / QUST_QOBJ / QUST_QTYP_0 bis QUST_QTYP_5**: *Quest*. Quest-Steuerungsdatensätze.
*   **RACE / RACE_Override**: *Race*. Definitionen von spielbaren und nicht-spielbaren Rassen, Kreaturen-Skeletten oder Eigenschaften.
*   **REFR / REFR_Buried / REFR_Deleted / REFR_Disabled**: *Placed Object Reference*. Konkrete Platzierung eines Objekts in einer Zelle (z. B. gelöscht, deaktiviert, vergraben).
*   **REGN / REGN_Override**: *Region*. Geografische Planeten-Regionen, die Klimazonen und Wetterverteilungen verknüpfen.
*   **RSPJ**: *Space Project*. Definition von Sternensystemen und Galaxien-Projektionen.
*   **SFBK / SFBK_Override**: *Starfield Planet Block*. Registrierungs- und Platzierungseinträge für prozedurale Planetengenerierung (POIs).
*   **Shifter_Quest_Chest / Shifter_Quest_Ship / Shifter_Quest_Starter / Shifter_Quest_Trader**: Berechnete Koeffizienten (0.0 bis 1.0), die beschreiben, wie eine Quest ins Spiel injiziert wird (z. B. Händler, Truhen).
*   **SHST / SHST_Override**: *Ship Structure*. Bauteile und Triebwerksparameter von Schiffen.
*   **SMOD / SMOD_Override**: *Ship Module*. Waffen, Schilde, Antriebe und Reaktoren für Raumschiffe.
*   **SNDR / SNDR_Override**: *Sound Descriptor*. Sound-Einstellungen (Lautstärke, Hall, Reichweite).
*   **SOUN**: *Sound*. Verweise auf Audio-Dateien.
*   **SPAC / SPAC_Override**: *Spaceship*. Raumschiffe und deren Kern-Layouts.
*   **SPEL / SPEL_Override / SPEL_Remove**: *Spell*. Zauber, Fähigkeiten und Krankheiten.
*   **STAT / STAT_Override**: *Static*. Unbewegliche 3D-Modelle (Häuser, Felsen, Wände).
*   **STBH**: *Ship Behavior*. Verhaltensdefinitionen für Schiffsteile (z. B. begehbare Luken, Türen und Wände in Habs).
*   **STDT**: *Star*. Daten und Eigenschaften für Sonnen/Sterne (z. B. Sternenfarben, Helligkeit).
*   **STMP**: *Ship Template*. Schablonen/Vorlagen für Raumschiffe.
*   **STND**: *Ship Node*. Anschlusspunkte (Snap-Nodes) für Schiffsteile.
*   **TERM**: *Terminal*. Interaktive Computerterminals.
*   **TREE / TREE_Override / TREE_Remove**: *Tree*. Baum-Definitionen und größere Landschaftsvegetationsobjekte.
*   **TXST**: *Texture Set*. Texturdefinitionen für 3D-Modelle.
*   **VEHI / VEHI_Override**: *Vehicle*. Landfahrzeuge (z. B. der REV-8 oder Moonjumper).
*   **VFXS / VFXS_Override / VFXS_Remove**: *Visual Effect*. Partikeleffekte (Rauch, Funken, Explosionen).
*   **VMOD / VMOD_Override**: *Vehicle Module*. Modifikationen und Ausbaustufen für Landfahrzeuge.
*   **WEAP / WEAP_Override / WEAP_KWDA_Helper / WEAP_KWDA_Ship / WEAP_KWDA_Vehicle**: *Weapon*. Waffen aller Art (Handfeuer-, Fahrzeug-, Schiffswaffen oder Hilfswerkzeuge).
*   **WRLD**: *Worldspace*. Ganze Planetenoberflächen oder große Außenbereiche.
*   **WTHR / WTHR_Override**: *Weather*. Wetter-Definitionen (Niederschlag, Wolken, Wind).
