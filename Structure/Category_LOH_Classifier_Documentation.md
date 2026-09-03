### Regel-Hierarchie & Ablaufplan - Category_LOH_Classifier (Semantische Pipeline)
Stand: August 2026

Die Klassifizierung erfolgt über eine dynamische, tabellengesteuerte Ausschlussmatrix (`PIPELINE_STEPS` und `StepContext`). Jede Mod-Komponente startet mit dem Standardwert `1` für alle Kategorien. Nach jedem semantischen Teilschritt zieht der Gewinner auf `curr_level` ein, während unbeteiligte Mods im Lockstep nachgezogen werden.

#### Phase A: Ausschlussprüfungen (Filterung)

##### 1. Ausschlussregeln (Rohdaten)
Schließt Kategorien auf Stufe 0 aus, falls grundlegende technische Record-Signaturen fehlen (z. B. keine Waffen-Forms für Waffen, keine Kleidungs-Forms für Kleidung etc.):
- `Skins`: Ausgeschlossen, wenn keine Ausrüstungs-Modifikationen (`OMOD`), Textur-Sets (`TXST`), Skin-Keywords (`CLFM_Skin`) oder Ausrüstungs-Overrides vorliegen (isolierte `LMSW`-Material-Swaps ohne Ausrüstungsbezug gelten als reine Mesh-Shader).
- `Städte`: Ausgeschlossen, wenn keine eigenen Stadt-Locations, keine Stadt-/Siedlungs-Zellen mit baulichen Strukturen vorliegen (reine Passanten-Zuweisungen `CrowdRegion` ohne Stadtzellen/Strukturen scheiden aus).
- `Schiffe`: Erkennt Schiffsbauteile (`COBJ_Ship`/`GBFM`), Schiffswaffen, Snap-Nodes (`STBH`/`STMP`) und Schiffs-Habs (`qry_CELL_Ship_PackIn`); reine Beleuchtungs-Overrides in Schiffszellen ohne Schiffshardware scheiden aus.

##### 2. Ausschlussregeln (Dummies & Hilfsobjekte)
Prüft für alle noch aktiven Kategorien (Wert == 1), ob nach Abzug von Dummies, Script-Helpern und abgeleiteten Modulen noch echte Netto-Inhalte (`dim_calc_outer_* > 0` oder `dim_calc_inner_* > 0`) vorliegen. Kategorien mit Netto-Inhalt == 0 werden in der Matrix auf `0` gesetzt:
- `Kleidung`: Ausgeschlossen, wenn alle ARMO `ARMO_Dummy` sind.
- `NPCs`: Ausgeschlossen, wenn alle NPCs `NPC__Dummy` oder Begleiter/Kreaturen sind.
- `Begleiter`: Ausgeschlossen, wenn alle NPCs `NPC__Dummy` sind (reine Mannequins/Schaufensterpuppen ohne KI-Pakete).
- `Kreaturen`: Ausgeschlossen, wenn keine Kreaturen-Keywords (`NPC__KYWD_Creature == 0`) vorliegen und alle vorhandenen NPCs `NPC__Dummy` sind (reine Mannequin-Rassen).
- `Waffen`: Ausgeschlossen, wenn alle Waffen Script-Helper, Schiffs- oder Fahrzeugwaffen sind.
- `Crafting`: Ausgeschlossen, wenn alle Rezepte Schiffs- oder Außenpostenmodule sind.
- `Einrichtung`: Ausgeschlossen, wenn alle Möbel Fahrzeug-Steuersitze sind.
- `Gebäude`: Ausgeschlossen, wenn vorhandene Zellen reine Workshop-PackIns oder Test-/Snapshoträume für Baupläne (`COBJ`/`PKIN`) ohne Worldspace (`WRLD == 0`), ohne Surface-Blocks (`SFBK == 0`) und ohne Dungeons (`LCTN_KYWD_Dungeon == 0`) sind.

#### Phase B: Zwingende System-Prioritäten (Typ 2)
- **Priorität BGS:** Offizielle Bethesda-Mods (`Author == Bethesda`) setzen sich per System-KO (Typ 2) durch.
- **Priorität Bugfix:** Reine Bugfix- und Fehlerbehebungs-Patches (hohe Override-Ratio & Kategorienbreite) setzen sich per System-KO (Typ 2) durch.
- **Priorität Overhaul:** Übergreifende Gesamtrevisionen (Overhauls mit breiten Eingriffen über mehrere Hauptbereiche) setzen sich per System-KO (Typ 2) durch.
- **Priorität Quest:** Echte Quest-Definitionen (`QUST` mit Stufen-Logik) setzen sich per System-KO (Typ 2) durch.

#### Phase C: Binnengruppen-Gewinner (Innergruppen-Resolution)
- **Gewinner Gruppe Welt-Mods:** Kaskadierende Auswahl des stärksten Welt-Merkmals (`POIs`, `Städte`, `Spielerheime`, `Gebäude`, `Außenposten`, `Umgebung`).
- **Gewinner Gruppe Objekt-Mods:** LLO-Kaskade (`Waffen` > `Kleidung` > `Crafting` > `Items` / `Skins` / `Einrichtung` / `Pflanzen`) sowie Massevergleich `dim_calc_outer_*`.
- **Gewinner Gruppe Sensorik:** LLO-Kaskade (`Licht` > `Effekte` > `Texturen` / `Sound`) sowie Massevergleich `dim_calc_outer_Texturen` vs. `dim_calc_outer_Sound`.
- **Gewinner Gruppe Akteure:** Bereinigung von Kreaturen ohne echte Monster-/Alien-Akteure (`NPC__KYWD_Creature == 0`); LLO-Kaskade (`Begleiter` / echte `Kreaturen` > `NPCs`) sowie Massevergleich `dim_calc_outer_Begleiter` vs. `dim_calc_outer_Kreaturen`.
- **Gewinner Gruppe Systeme:** `Gameplay` / `Sortierung` / `Interface` stechen `Tweaks` per KO aus; Massevergleich unter Inhalts-Systemen; `Tweaks` als Auffangbecken.
- **Gewinner Gruppe Transport:** Massevergleich `dim_calc_outer_Schiffe` vs. `dim_calc_outer_Fahrzeuge`.
- **Echte Remover-Mods:** Rein subtraktive Lösch-Mods stechen leere Welt- und Hilfsstrukturen per KO aus; bei echten neuen Inhalten scheidet `Remove` per KO aus.
- **Vorrang Inhalt vor Sensorik:** Aktive Inhalts-Kandidaten stechen passive Sensorik (Texturen/Sounds) per KO aus. Reines Beleuchtungs- und Shader-Overhauls (`Licht`/`Effekte`) ohne bauliche Neubauten (`has_new_structures == False`) stechen reine Weltzellen-Modifikationen per Render-Architektur aus.

#### Phase D: Gruppenduelle (Metagruppen-Duelle)

> [!IMPORTANT]
> **Allgemeingültiges Prinzip für alle Gruppenduelle:**
> 1. **Verlässlichkeit aktiver Kategorien:** Wir verlassen uns strikt darauf, dass eine Kategorie, die auf der jeweiligen Stufe noch aktiv ist (`Wert == Stufe`), alle inhaltlichen und technischen Bedingungen für diese Kategorie vollumfänglich erfüllt (garantiert durch die Ausschlussmatrix in Phase A, den Dummyausschluss und die Prioritäts- und Gruppengewinner in den Phasen B und C). Dies ermöglich auch einen einfachen Vergleich nach noch aktiven Kategorien in der vorhanden Ausschlussmatrix (Beispiele für die Planung und Umsetzung können aus bereits umgesetzten Gruppenduellen entnommen werden.)
> 2. **Keine Neuerfindung von Grundregeln:** In den Duellschritten werden keine neuen Einstiegs- oder Existenzregeln für Kategorien erfunden (keine redundanten Re-Validierungen von Signaturen, Datensätzen oder Basis-Berechtigungen).
> 3. **Zusatzprüfungen nur für die Duell-Entscheidung:** Es werden ausschließlich solche zusätzlichen technischen Kriterien herangezogen, die für die Abwägung zwischen den zwei konkreten Duellanten notwendig oder sinnvoll sind:
>    * **Typ 3 (Architektur-K.O.):** Nach unserem Hauptgrundsatz der Kategorisierung nach den Vorgaben und Arbeitsweise der Creation Engine 2 bevorzugen wir klare und treffsichere Regelungen vor Massenvergleichen. Wir gleichen dies zur Sicherheit auch immer gegen die LLO Regeln ab.
>    * **Typ 4 (Massenvergleich mit relationalen Gewichtungsfaktoren):** Standardisierter Vergleich der Dimensionen `dim_calc_outer_*`.
>      * *Wichtig (Gewichtungsfaktoren):* Da unterschiedliche Kategorien in der Creation Engine 2 eine stark abweichende natürliche Datendichte aufweisen (z. B. 1–3 hochkomplexe `PERK`-/`MGEF`-Gameplay-Einträge oder Begleiter-KI vs. 50+ einfache Rezept- oder Möbel-Einträge `COBJ`/`FURN`), kommen bei Typ 4 **definierte Gewichtungsfaktoren** (z. B. 3-facher Schwellenwert für Charakter, Begleiter oder Gameplay) zum Einsatz, um ein faires Kräfteverhältnis sicherzustellen.

Nach der Bestimmung der Binnengruppen-Gewinner ist pro Meta-Gruppe maximal ein Gewinner aktiv. Die finale Auflösung erfolgt über die folgenden Gruppenduelle:

##### Block 1: Transport-Duelle
- **Gruppenduell Transport vs. Objekte:** Echte Transportbauteile stechen Einrichtungs-Zuweisungen und Skins per Architektur-KO aus; freie Objekte per Massevergleich.
- **Gruppenduell Transport vs. Charakter:** Echte Transportbauteile stechen Charakter-Styling per LLO-KO aus.
- **Gruppenduell Transport vs. Systeme:** Transportkomponenten stechen Hilfssysteme (Tweaks, Sortierung, Interface) per KO aus; gegenüber Gameplay greift Architektur-KO für Hardware bzw. gewichteter Massevergleich.
- **Gruppenduell Transport vs. Akteure:** Schiffsteile stechen reine Crew per Architektur-KO aus; Begleiter bleiben geschützt.
- **Gruppenduell Transport vs. Welt:** Reine Habs ohne Welt-Navmesh -> Transport gewinnt; Städtische Nahverkehrssysteme, Dungeons oder echte Werft-Siedlungen -> Welt gewinnt.

##### Block 2: Objekt-Duelle
- **Gruppenduell Objekte vs. Charakter:** Handwaffen und Kleidung schlagen Charakter per KO; Skins unterliegen Charakter per KO; Crafting/Einrichtung/Items/Pflanzen vs. Charakter per gewichtetem Massevergleich.
- **Gruppenduell Objekte vs. Systeme:** Physische Objekte stechen Einstellungen (`Tweaks`), eigene Objekte `Sortierung` und Ausrüstung `Interface` per KO aus; `Gameplay`-Mechaniken stechen Beiwerk-Items/Skins per KO aus; Massevergleich bei Crafting/Einrichtung/Pflanzen vs. Gameplay.
- **Gruppenduell Objekte vs. Akteure:** Dummies/Mannequins unterliegen Objekten per KO; dominante Objekt-Sammlungen übertreffen NPCs; ansonsten Massevergleich.
- **Gruppenduell Objekte vs. Welt:** Mod-eigene Hilfsobjekte (Kisten/Werkbänke in bestehenden Zellen) dienen der Übergabe $\rightarrow$ Objekt gewinnt per KO; echte neue Raumstrukturen $\rightarrow$ Welt gewinnt per KO; ansonsten Massevergleich.

##### Block 3: Charakter-Duelle
- **Gruppenduell Charakter vs. Systeme:** `Gameplay` gewinnt per Architektur-KO (Typ 3) vor `Charakter` (Funktionale Spiellogik/Zauber/Tränke vor reinem Aussehen); `Charakter` gewinnt per Architektur-KO (Typ 3) vor `Tweaks`, `Sortierung` und `Interface`.
- **Gruppenduell Charakter vs. Akteure:** `Begleiter` gewinnt per Architektur-KO (Typ 3) vor `Charakter` (Begleiter-KI und Logik besitzen funktionale Priorität); bei `NPCs` entscheidet ein gewichteter Massevergleich (Typ 4 mit 3-fachem Faktor für `Charakter`); bei `Kreaturen` gewinnt `Charakter` per Architektur-KO (Typ 3), wenn keine Kreaturen-Akteure vorhanden sind (`NPC__KYWD_Creature == 0`), andernfalls besitzen echte Spielwelt-Kreaturen Priorität (Typ 3) bzw. gewichteter Massevergleich (Typ 4).
- **Gruppenduell Charakter vs. Welt:** Physische Welt- und Raumgeometrie (`Städte`, `Gebäude`, `Spielerheime`, `POIs`, `Umgebung`) stechen `Charakter` ausnahmslos per Architektur-KO (Typ 3) aus (Ladeordnungs-Priorität für NavMeshes, Ladezonen und Geometrie); bei `Außenposten` entscheidet ein gewichteter Massevergleich (Typ 4 mit 3-fachem Faktor für `Charakter`).

##### Block 4: Akteure-Duelle
- **Gruppenduell Akteure vs. Systeme:** Lebendige Spielwelt-Akteure (`Begleiter`, `NPCs`, `Kreaturen`) mit Physis, KI-Paketen (`PKID`), Sprachausgabe und Weltplatzierung stechen alle System-Kategorien (`Gameplay`, `Sortierung`, `Interface`, `Tweaks`) ausnahmslos per Architektur-KO (Typ 3) aus (Ladeordnungs-Priorität LLO Pos 14–16 vor Pos 13; mitgelieferte Zauber, Perks, Kampffähigkeiten oder Einstellungs-Globale dienen als Werkzeuge/Fähigkeiten der Akteure).
- **Gruppenduell Akteure vs. Welt:** Physische Welt- und Raumgeometrie (`Städte`, `Gebäude`, `Spielerheime`, `POIs`, `Umgebung`) stechen lebendige Akteure (`Begleiter`, `NPCs`, `Kreaturen`) ausnahmslos per Architektur-KO (Typ 3) aus (Ladeordnungs-Priorität LLO Pos 05–08 und 11 vor Pos 14–16 für PreVis, NavMeshes, Ladezonen und Planetenblöcke); bei `Außenposten` schlägt `Begleiter` Baurezepte per Architektur-KO (Typ 3, LLO Pos 15 vor Pos 09), modulare Bausysteme (`COBJ_BNAM_Outpost_* > 0`) schlagen Akteure per Architektur-KO (Typ 3, LLO Pos 09 vor Pos 14/16) und bei reinen Crew-/Akteur-Sammlungen entscheidet ein gewichteter Massevergleich (Typ 4 mit 3-fachem Faktor für Akteure).

##### Block 5: Systeme-Duelle
- **Gruppenduell Systeme vs. Welt**

#### Phase E: Auswertung & Zuweisung
Am Ende jedes Pipeline-Durchlaufs/Schritts wird für jede Mod-Komponente das Maximum (`max_val > 0`) der verbleibenden Matrix-Werte ermittelt:
* Wenn **genau eine** Kategorie diesen Höchstwert aufweist, gilt die Mod als eindeutig klassifiziert und dieser Wert wird als `Category_LOH_Classifier` eingetragen.
* Wenn mehrere Kategorien denselben Höchstwert aufweisen (oder alle auf `0` stehen), bleibt die Klassifizierung unbestimmt (`NULL`) und zieht in den nächsten Prüfschritt ein.

#### Phase F: Transparenz-Protokollierung (`LoadOrder_Classifier_Results` & `Classifier_Result_Types`)
Um dem Benutzer transparent und nachvollziehbar zu begründen, warum eine Modifikation in eine bestimmte Kategorie eingestuft wurde (und warum andere Kategorien ausgeschlossen wurden), führt der Classifier eine verlierergetriebene Protokolltabelle `LoadOrder_Classifier_Results`.

##### A. Stammdaten: `Classifier_Result_Types`
Definiert die 4 normierten Entscheidungstypen:
* `1` – **`Inhalt`**: Ausschluss wegen vollständigen Fehlens technischer Datensätze/Assets in der Mod (Ausschlussprüfungen).
* `2` – **`Zwingend`**: Zwingende System-Präzedenz übergeordneter Mod-Klassen (BGS-Original, Bugfix-Patch, Overhaul, echte Quest-Steuerung).
* `3` – **`Architektur`**: Vorrangentscheidung basierend auf der Subsystem- und Objekthierarchie der Creation Engine 2 (Träger vor Skin, Rendering-Tiefe Licht > Textur, Welt-NavMesh vor Einzelplatzierung in Binnengruppen und Gruppenduellen).
* `4` – **`Masse`**: Quantitative Vorrangentscheidung nach Datenvolumen (`dim_calc_outer_*`) bei gleichrangigen Inhalten (inklusive relationaler Gewichtungsfaktoren bei unterschiedlicher natürlicher Datendichte, z. B. bei Charakter, Begleitern oder Gameplay-Mechaniken).

##### B. Bewegungstabelle: `LoadOrder_Classifier_Results`
Speichert für jede in einem Prüfschritt ausgeschiedene Kategorie genau einen Datensatz:
* `PRIMARY KEY (Step_ID, Mod_ID, Component_ID, CategoryLOH_ID_Looser)`
* `Step_Description`: Semantische Bezeichnung des Prüfschritts aus der Pipeline-Steuerung (z. B. "Ausschlussregeln (Rohdaten)", "Gruppenduell Transport vs. Objekte").
* `CategoryLOH_ID_Winner`: Sieger-Kategorie des Duells/Schritts (bei Ausschlussprüfungen `NULL`).
* `Type_ID`: Fremdschlüssel auf `Classifier_Result_Types(ID)`.
* `Reason`: Technische und verständliche Begründung der Ausschlussentscheidung.

##### C. Ergebnissicht: `View_LoadOrder_Classifier_Results`
Stellt die Protokolldaten für die Benutzeroberfläche flach und chronologisch bereit:
* **Spalten:** `Mod_ID`, `Mod_Name`, `Component_ID`, `Component_File`, `Step_ID`, `Step_Description`, `CategoryLOH_Position_Looser`, `CategoryLOH_Looser`, `CategoryLOH_Winner`, `Type`, `Reason`.
* **Sortierung:** `ORDER BY Mod_ID, Component_ID, Step_ID, CategoryLOH_Position_Looser` (ermöglicht die lückenlose Nachverfolgung des Entscheidungsweges pro Mod/Komponente entlang aller Prüfschritte).