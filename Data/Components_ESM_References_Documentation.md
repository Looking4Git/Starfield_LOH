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
*   **Shifter_Quest_Starter / Shifter_Quest_Trader / Shifter_Quest_Chest / Shifter_Quest_Ship**: Berechnete Koeffizienten (0.0 bis 1.0), die beschreiben, wie eine Quest ins Spiel injiziert wird (z. B. über Händler, Truhen oder Terminals).
*   **DIAL / DIAL_Override**: *Dialogue Branch*. Dialogthemen und -zweige.
*   **INFO / INFO_Override**: *Dialogue Info*. Einzelne gesprochene Sätze und Reaktionen innerhalb von Dialogen.
*   **GLOB / GLOB_Override**: *Global Variable*. Globale Variablen zur Systemkonfiguration oder Tweak-Steuerung.

---

## 3. Gravity 2: World & Structure (Weltplatzierungen und Strukturen)

*   **WRLD**: *Worldspace*. Ganze Planetenoberflächen oder große Außenbereiche.
*   **CELL / CELL_Override / CELL_Override_PackIn / CELL_PackIn**: *Cell*. Einzelne Planetenquadrate (Außenbereiche) oder Ladezonen (Innenräume). `CELL_Override_PackIn` erfasst Zell-Überschreibungen, bei denen die Editor-ID auf ein Pack-In oder eine Storage-Schablonenzelle hinweist (z. B. enthaltend "packin"). `CELL_PackIn` erfasst neu angelegte Zellen, die als Pack-In-Storage-Schablonenzellen deklariert sind.
*   **NVNM / NAVM**: *NavMesh*. Navigationspfade für Begleiter und NPCs. Zeigt an, dass die Wegfindung modifiziert oder neu angelegt wurde.
*   **REFR**: *Placed Object Reference*. Konkrete Platzierung eines Objekts in einer Zelle (z. B. eine Kiste, ein Tisch, ein NPC).
*   **STAT / STAT_Override**: *Static*. Unbewegliche 3D-Modelle (Häuser, Felsen, Wände, Deko-Objekte).
*   **MSTT / MSTT_Override**: *Movable Static*. Bewegliche statische Objekte (z. B. Becher, physikalisch bewegliche Dekorationsgegenstände, Gerüste).
*   **FURN / FURN_Override**: *Furniture*. Möbel und interaktive Stationsplatzierungen (Stühle, Betten, Werkbänke).
    *   **FURN_VMRT** (*Vehicle Mount*): Plätze für Fahrzeuginsassen (Sitze).
    *   **FURN_VCMT** (*Vehicle Camera*): Kameraperspektiven an Fahrzeugen.
    *   **FURN_VWWD** (*Vehicle Wheels*): Radaufhängungen und Radplatzierungen für Landfahrzeuge.
    *   **FURN_VCTT** (*Vehicle Controls*): Cockpit-Steuerungen für Fahrzeuge.
*   **TERM**: *Terminal*. Interaktive Computerterminals.
*   **LCTN / LCTN_Override**: *Location*. Definitionen von Orten, Städten, Dungeons oder Points of Interest (POI).
    *   **LCTN_KYWD_City**: Zähler für Standorte, die als Stadt klassifiziert sind (Keyword `0x22611` und `"city"` in der Editor-ID).
    *   **LCTN_KYWD_Settlement**: Zähler für Standorte, die als normale Siedlung klassifiziert sind (Keyword `0x22611` und kein `"city"` in der Editor-ID).
    *   **LCTN_KYWD_Playerhome**: Zähler für Standorte, die als Spielerheim klassifiziert sind (Keyword `0x2ef272`).
    *   **LCTN_KYWD_Dungeon**: Zähler für Standorte, die als Dungeon klassifiziert sind (Keyword `0x254bc`).
*   **FLOR / FLOR_Override**: *Flora*. Pflanzen-Definitionen, erntebare organische Ressourcen und Gewächshaus-Erzeugnisse.
*   **TREE / TREE_Override**: *Tree*. Baum-Definitionen, größere Landschafts- und Waldvegetationsobjekte.
*   **WTHR / WTHR_Override**: *Weather*. Wetter-Definitionen (Niederschlag, Wolken, Wind, Himmelsfarben).
*   **CLMT / CLMT_Override**: *Climate*. Klimazyklen (Tag-Nacht-Rhythmen, Wetterverteilungen für Planeten).
*   **REGN / REGN_Override**: *Region*. Geografische Planeten-Regionen, die Klimazonen und Wetterverteilungen verknüpfen.

---

## 4. Gravity 3: Gameplay & Actors (Charaktere, Werte und Gameplay-Logik)

*   **NPC_ / NPC__Override**: *Non-Player Character / Actor*. Charakter-Definitionen (Gegner, Begleiter, Händler, Kreaturen).
*   **ACHR**: *Actor Reference*. Platzierte Instanz eines NPCs in der Spielwelt.
*   **PKIN**: *Pack-In*. Vorgefertigte Gruppen von Objekten, die zusammen in die Welt geladen werden (oft für POIs / Außenposten).
*   **PERK / PERK_Override**: *Perk*. Fertigkeiten, Skills und passive Eigenschaften.
*   **AVIF / AVIF_Override**: *Actor Value Information*. Attribute, Fraktionsbeziehungen und Statuswerte (z. B. Gesundheit, Tragekapazität).
*   **MOVT**: *Movement Type*. Bewegungseigenschaften (Geschwindigkeit, Beschleunigung für Gehen, Laufen, Fliegen).
*   **NPC_KYWD_Ship / NPC_KYWD_Companion / NPC_KYWD_Creature / NPC_KYWD_Shop**: Kategorisierte Zählung von NPCs basierend auf ihren internen Editor-IDs (z. B. Händler, Begleiter, Monster, Schiffstechniker).
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
*   **IMAD / IMAD_Override**: *Image Space Modifier*. Post-Processing-Shader, Farbkorrekturen (Farbton, Helligkeit, Sättigung, Depth of Field) für Wetter und Bildschirmeffekte.

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
*   **COBJ_BNAM_Outpost_Heavy**: Zähler für rezepthinterlegte Außenposten-Kernkomponenten (Extraktoren `0x00008406`, Stromgeneratoren `0x0005A6DE`, Verteidigungsanlagen `0x001E6641`, Fabrikatoren `0x002731A0`). Weist eindeutig auf eine funktionale Außenposten-System-Mod hin.
*   **COBJ_BNAM_Outpost_Soft**: Zähler für rezepthinterlegte Außenposten-Struktur- und Dekoelemente (Habs `0x002A7578`, Missionstafeln/Crewstationen `0x0006D72D`, Innenausstattungen `0x000E6A3E`, Roboter `0x001D9F5F`, Container/Lagerplätze `0x0027319A`, Werkbänke `0x002CFDE6`). Kann sowohl in Außenposten- als auch in reichhaltigen Einrichtungsmods vorkommen.
*   **COBJ_BNAM_Ship**: Rezepte für den Schiffsbau-Editor (Shipbuilder). Erkennung durch Abgleich der Workbench (`BNAM`) gegen das Schiffbau-Keyword `workbenchshipbuildingkeyword` (`0x0029C480`).
*   **SPAC / SPAC_Override**: *Spaceship*. Raumschiffe und deren Kern-Layouts.
*   **SHST / SHST_Override**: *Ship Structure*. Bauteile und Triebwerksparameter von Schiffen.
*   **SMOD / SMOD_Override**: *Ship Module*. Waffen, Schilde, Antriebe und Reaktoren für Raumschiffe.
*   **GBFM**: *Gameplay Blueprint*. Allgemeine Gameplay-Blaupausen (wird in Starfield für Schiffskomponenten, Landfahrzeug-Zuweisungen und NPC-Spawnzonen/Crowd-Regionen verwendet).
*   **GBFM_EDID_CrowdRegion**: Zähler für Gameplay-Blaupausen (`GBFM`), die anhand ihrer Editor-ID (`EDID`) eindeutig als städtische NPC-Spawnzonen (Crowd-Regionen) identifiziert wurden. Dient zur Bereinigung der echten Schiffskonfigurationen in der Ausschlussmatrix.
*   **GBFM_EDID_Vehicle**: Zähler für Gameplay-Blaupausen (`GBFM`), die anhand ihrer Editor-ID (`EDID`) als Landfahrzeug-Designs/Steuerungen identifiziert wurden. Dient ebenfalls zur Bereinigung der echten Schiffskonfigurationen in der Ausschlussmatrix.
*   **SFBK / SFBK_Override**: *Starfield Planet Block*. Registrierungs- und Platzierungseinträge für prozedurale Planetengenerierung (POIs).
*   **PCBN**: *Planet Content Block Node*. Knotenpunkte des Planet Content Managers (PCM) zur dynamischen Verteilung von POIs in der Galaxis.
*   **PCCN**: *Planet Content Connection*. Verknüpfungen des Planet Content Managers (PCM) zur Einspeisung von Custom-POIs in das prozedurale Spawnsystem.
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
*   **INNR / INNR_Override**: *Instance Naming Rules*. Namensregeln zur dynamischen Namensvergabe von Gegenständen wie Waffen und Rüstungen. Wird primär für Sortierungs-Mods (Item Sorters) verwendet.

---

## 7. Spezifische Bereinigungsspalten (Lösch- und Deinstallations-Flags)

*   **REFR_Deleted / REFR_Disabled / REFR_Buried**: Zähler für Modifikationen, die Objekte aus der Spielwelt entfernen (gelöscht, deaktiviert oder unter die Erde vergraben).
*   **SPEL_Remove / MGEF_Remove / EFSH_Remove / ENCH_Remove / VFXS_Remove / ALCH_Remove / PERK_Remove / FLOR_Remove / TREE_Remove**: Instanzen, bei denen bestehende Statuseffekte, Effekte, Rüstungseigenschaften, Partikeleffekte, Rezepte/Tränke, Perks, Pflanzen oder Bäume gezielt über eine Modifikation aus dem Spielsystem deinstalliert/entfernt werden.
