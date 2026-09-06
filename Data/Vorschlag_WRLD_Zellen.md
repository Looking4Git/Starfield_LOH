# Konzeptvorschlag: Harmonisierung von Außenzellen über Worldspace-Standorte

**Dokument-ID:** `Vorschlag_WRLD_Zellen.md`  
**Datum:** 06.09.2026  
**Status:** Zur Besprechung und Freigabe für die Implementierung  
**Autor:** Antigravity & Software-Architekt / Product Manager  

---

## 1. Ausgangslage & das bisherige Dilemma bei Mod 37

Am Beispiel von Mod 37 (*nat_falklands_compatibility_patch.esm*, Component ID 157) trat bei der Klassifizierung ein fundamentales Dilemma zutage:

### 1.1 Die tatsächlichen Rohdaten von Mod 37
* `WRLD_Override = 1` *(New Atlantis Worldspace, ID 75035)*
* `CELL_Override = 2` *(die Kacheln 75036 [Persistent] und 75153 [Headquarters] in New Atlantis)*
* `REFR = 3` *(die im Stadtgebiet platzierten Objekte)*

### 1.2 Warum Mod 37 bisher als "Umgebung" eingestuft wurde
In `View_Components_References_Calc` wird die Wildnis/Umgebungs-Kennzahl bisher wie folgt berechnet:
$$\text{calc\_CELL\_Override\_Environment} = \text{CELL\_Override} - \text{qry\_CELL\_Override\_City} - \text{qry\_CELL\_Override\_Settlement} - \dots$$

Da die beiden Kacheln `75036` und `75153` in der Mod keinen eigenen `XLCN`-Standortzeiger tragen (da Außen-Kacheln in der Creation Engine den Standort automatisch vom übergeordneten `WRLD 75035` erben), ergab die Abfrage:
* `qry_CELL_Override_City = 0`
* Folglich: $\text{calc\_CELL\_Override\_Environment} = 2 - 0 = \mathbf{2}$

Zusätzlich floss `WRLD = 1` bisher pauschal in `dim_calc_outer_Umgebung` ein.  
**Ergebnis bisher:** Das System sah **3 Umgebungspunkte** (1 Worldspace + 2 Zellen) und **0 Städtepunkte** $\rightarrow$ Falschklassifizierung als `Umgebung`.

### 1.3 Warum eine reine `WRLD`-Addition das Problem nicht gelöst hätte
Würde man lediglich `WRLD` als Stadt werten, aber die Zellen unberührt lassen, stünde es:
* `Städte:` **1 Punkt** *(aus dem Worldspace)*
* `Umgebung:` **2 Punkte** *(aus den beiden Kacheln, die immer noch fälschlich als Wildnis berechnet werden!)*

Die Mod wäre weiterhin in `Umgebung` hängengeblieben.

---

## 2. Der Architekturvorschlag: Auflösung der Außenzellen

Statt `WRLD` als unhandliche, separate Maßeinheit neben den Zellen in die Klassifizierungsregeln einzuführen, verfolgen wir den architektonischen Ansatz:

> **Außenwelt-Kacheln erben den Typ ihres Worldspaces und fließen direkt in die bestehenden `CELL`-Zähler (`qry_CELL_City`, `qry_CELL_Settlement`) ein.**

### 2.1 Warum dieser Ansatz architektonisch überlegen ist
1. **Einheitliche Währung:** Das Gesamtsystem rechnet weiterhin sauber auf Zellebene. Es gibt keine Verbiegung von Formeln durch heterogene Datentypen.
2. **Keine Doppelzählung:** Innenräume bleiben Innenräume, und Außenkacheln werden genau als das gewertet, was sie sind: Kacheln einer Stadt.
3. **Automatische Bereinigung der Wildnis:**  
   Sobald die beiden Kacheln in `qry_CELL_Override_City` gezählt werden, greift die Subtraktion:  
   $$\text{calc\_CELL\_Override\_Environment} = 2 - 2 = \mathbf{0}$$  
   Die falsche Umgebung sinkt für Mod 37 augenblicklich auf Null!
4. **Minimalinvasiv (Null Folgeaufwand im Classifier):**  
   Alle 29 Schritte der Klassifizierungs-Pipeline (`Category_LOH_Classifier.py`), alle K.O.-Kriterien und alle `dim_calc`-Werte bauen bereits auf `qry_CELL_City` auf. Sie greifen sofort und fehlerfrei, ohne dass der Python-Code des Classifiers grundlegend umgeschrieben werden muss!

---

## 3. Umsetzungsplan für den nächsten Schritt

### Schritt 1: Zuordnung der Außenzellen zum Worldspace
In Bethesda-ESM-Dateien befinden sich Außen-Zellen innerhalb einer `GRUP` vom Typ 1 (`WRLD_CHILDREN`), deren Label der FormID des Worldspaces entspricht.  
Wir haben zwei Wege zur Zuordnung:

* **Weg 1 (Relational über Mod-Scope):**  
  Wenn eine Mod einen verifizierten Stadt-Worldspace überschreibt (`qry_WRLD_Override_City > 0`) und Außenzellen besitzt, werden diese Kacheln in `View_Components_References_Qry` direkt den Stadt-Zellen zugerechnet.
* **Weg 2 (Präzise Zuordnung über den Parser):**  
  Der Single-Pass-Parser merkt sich beim Durchlaufen der `GRUP Type 1` den aktuellen `parent_wrld_id` für jede `CELL`.

### Schritt 2: Aktualisierung von `View_Components_References_Qry`
Die Abfragen für `qry_CELL_City` und `qry_CELL_Override_City` werden so erweitert, dass sie sowohl Innenräume mit direktem `XLCN` als auch Außenzellen aus verifizierten Stadt-Worldspaces erfassen.

### Schritt 3: Simulation & Verifikation
* Simulation über alle 174 Mods der Datenbank.
* Bestätigung, dass Mod 37 sauber von `Umgebung` nach `Städte` wechselt.
* Verifikation, dass keine unbeabsichtigten Verschiebungen bei anderen Natur-/Wildnis-Mods auftreten.

---

## 4. Fazit
Dieser Ansatz löst die Ursache des Problems an der Wurzel: Er überbrückt die Lücke der Bethesda-Engine (fehlende `XLCN`-Einträge auf Außenkacheln) durch saubere relationale Vererbung und hält die Klassifizierungs-Pipeline schlank, verständlich und wartungsarm.
