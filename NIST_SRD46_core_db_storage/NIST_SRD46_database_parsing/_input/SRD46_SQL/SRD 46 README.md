# NIST SRD 46 SQL source

This directory contains the 19 original MySQL schema/data pairs used by the SRD 46 parser. Each `.sql` file defines a table's columns; its matching `.txt` file contains the rows in Windows-1252 (CP1252) encoding. Keep both files for every table. The parser reads them directly without a running MySQL server.

## Project licence

The project's original software and added documentation use the MIT licence below, as recorded in the repository [LICENSE](../../../../LICENSE), copyright (c) 2026 Yunkai Sun. The NIST source data retain the terms in the complete original README at the end of this document. The project licence does not replace those source-data terms. See also [NOTICE](../../../../NOTICE).

```text
MIT License

Copyright (c) 2026 Yunkai Sun

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Source attribution and processing

Source: National Institute of Standards and Technology, *Critically Selected Stability Constants of Metal Complexes*, NIST Standard Reference Database 46, Version 8.0 (2004), [doi:10.18434/M32154](https://doi.org/10.18434/M32154). The source database credits R. M. Smith and A. E. Martell for data collection and selection, and R. J. Motekaitis for the original program. Retain the scientific references for individual constants.

The MySQL export is dated 2011-08-30. NIST describes this SQL representation as an outside group's extraction; its original reliability disclaimer and reuse terms are reproduced below.

Project processing update, 2026-09-13: the pipeline reads these original schema/data files and applies 495 recorded source corrections and notation changes from the historical CSV exports through guarded rules. Source measurement values, qualifiers, identifiers, and full timestamps remain authoritative. The schema/data files in this directory are unchanged; corrections are applied while parsing and recorded in the staging ledger. PubChem enrichment, QupKake predictions, and calculated fingerprints remain separately identified project processing.

Run from `NIST_SRD46_database_parsing`:

```shell
python -B run_srd46_pipeline.py --pubchem cache-only
```

The unified runner no longer requires the removed `SRD46_SQL_and_CSV` or `pip1_parsed_individual_SRD46` folders. The PubChem and QupKake archives remain inputs for their corresponding enrichment modes. See the [parser README](../../README.md), [source-correction rules](../../srd46_pipeline/chem_rules_lib/source_corrections.py) and [source reader](../../srd46_pipeline/sources.py).

## Original NIST README (complete)

The original `SRD 46 README.txt` is reproduced in full below, with its wording unchanged. Only character encoding (CP1252 to UTF-8) and line endings (CRLF to LF) were converted for Markdown, with a final newline added to delimit the code block. A [byte-exact archival copy](../../../../docs/licenses/NIST_SRD46_README.txt) is retained separately with SHA-256 `069d578fd67930146d83b303057bf15faeffe905c64902da94a321afb2ab52d1`.

```text
NIST Standard reference Database 46
Critically Selected Stability Constants of Metal Complexes 

NOTE.  THIS DATABASE HAS BEEN DISCONTINUED.

*** OVERVIEW ***
NIST SRD 46 Version 8.0 for Windows is a major enhancement to this widely used database which provides comprehensive coverage of interactions for aqueous systems of organic and inorganic ligands with protons and various metal ions and is based on the six-volume Critical Stability Constants by Martell and Smith. The new version contains 225 additional ligands, new data, data printing, rapid bibliography searching and more streamlined commands. New literature has resulted in revision and upgrading of 30% of previous data. Entire contents are critically selected for accuracy and consistency.

For 6166 Ligands:
    112559 lines of data
    metal stability constants and related equilibrium constants
    thermodynamic constants
    a complete bibliography
    structural formulas
    search by empirical formulas and type of ligand
    protonation constants under specified conditions of temperature and ionic strength
    heats of protonation
    entropies of protonation
    metal/metal species searching capabilities
    author search


*** FILES ATTACHED ***
1.  SRD 46 Manual.pdf  This is a pdf of users' guide for the (older) Windows version of the database.

2.  SRD 46 Install.zip   This is a zip file containing an executable (exe) that install the program.
NOTE: This database is not compatible with 64 Bit systems.
System Requirements: PC running WindowsTM 95, 98, 2000, NT 4.0 Me,XP and Vista 32 bit operating system; hard disk with at least 12.7 MB free space. 
This database will run on Windows 7  using the Windows XP Mode – Virtual PC.  In order to run this program as is, it is suggest to 1) Run it on an old machine or 2) A number of people have been able to run it under Linux using the WINE emulator.

3.  SRD 46 SQL.zip  This is a zip file containing plain text and sql table dump files for use in constructing a SQL database.


*** DISCLAIMER ***
"BUYER BEWARE."  Data from SRD 46 has been put into a tabular (SQL) format by a third party. The file, SRD 46 SQL.zip, contains data which were extracted from the Windows database program by an outside group. NIST cannot vouch for its reliability. It is known that the structure database contains errors. The archive contains SQL files which will load data in accompanying text files into SQL tables.

*** FAIR USE OF NIST DATA ***
This data/work was created by employees of the National Institute of Standards and Technology (NIST), an agency of the Federal Government. Pursuant to title 17 United States Code Section 105, works of NIST employees are not subject to copyright protection in the United States.  This data/work may be subject to foreign copyright.

The data/work is provided by NIST as a public service and is expressly provided “AS IS.” NIST MAKES NO WARRANTY OF ANY KIND, EXPRESS, IMPLIED OR STATUTORY, INCLUDING, WITHOUT LIMITATION, THE IMPLIED WARRANTY OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, NON-INFRINGEMENT AND DATA ACCURACY. NIST does not warrant or make any representations regarding the use of the data or the results thereof, including but not limited to the correctness, accuracy, reliability or usefulness of the data. NIST SHALL NOT BE LIABLE AND YOU HEREBY RELEASE NIST FROM LIABILITY FOR ANY INDIRECT, CONSEQUENTIAL, SPECIAL, OR INCIDENTAL DAMAGES (INCLUDING DAMAGES FOR LOSS OF BUSINESS PROFITS, BUSINESS INTERRUPTION, LOSS OF BUSINESS INFORMATION, AND THE LIKE), WHETHER ARISING IN TORT, CONTRACT, OR OTHERWISE, ARISING FROM OR RELATING TO THE DATA (OR THE USE OF OR INABILITY TO USE THIS DATA), EVEN IF NIST HAS BEEN ADVISED OF THE POSSIBILITY OF SUCH DAMAGES.

To the extent that NIST may hold copyright in countries other than the United States, you are hereby granted the non-exclusive irrevocable and unconditional right to print, publish, prepare derivative works and distribute the NIST data, in any medium, or authorize others to do so on your behalf, on a royalty-free basis throughout the world.

You may improve, modify, and create derivative works of the data or any portion of the data, and you may copy and distribute such modifications or works. Modified works should carry a notice stating that you changed the data and should note the date and nature of any such change. Please explicitly acknowledge the National Institute of Standards and Technology as the source of the data:  Data citation recommendations are provided at https://www.nist.gov/open/license.

Permission to use this data is contingent upon your acceptance of the terms of this agreement and upon your providing appropriate acknowledgments of NIST’s creation of the data/work.
```
