# Student CyberTruck Experience Manual
 The book to accompany the student cybertruck experience.  A general introduction to heavy vehicle cybersecurity.

## Working on the Manual
The book is written with a program called LyX (www.lyx.org). This program is a graphical front end for the LaTeX typesetting engine. To work on the manual, please download and install LyX after intalling a LaTeX distribution. For windows users, the Miktex is the latex distribution of choice. 

The main document is 00_CyTeX_Manual_main_document.lyx. This main document contains the front matter and all the chapters are included as child documents. 

## References and the Bibliography

The file cytex.bib is a bibtex file for the referencs used in the manual. This file can be edited by a text editor or a more featured bibliography data base, like Jabref can be used as well. 

Be sure to use the `\url{}` construct in the notes section to include live hyperlinks to the sources referenced. 

## Branch Protection
The master branch is protected from direct commits. A reviewed pull request is required to merge any commits into the master branch. Therefore, please checkout or create new branches to add content. This way it can be reviewed before merge. 