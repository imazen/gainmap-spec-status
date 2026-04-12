## Digital photography

## metadata for image conversion

## Part 1:

## Dynamic range conversion

*Photographie numérique — Carte de gain pour la conversion*  *d’images —*

*Partie 1: Conversion de plage de dynamique*

[https://standards.iteh.ai/catalog/standards/iso/ef1c15f5-fbe6-421d-b145-887655776304/iso-21496-1-2025](https://standards.iteh.ai/catalog/standards/iso/ef1c15f5-fbe6-421d-b145-887655776304/iso-21496-1-2025)

Reference number  ISO 21496-1:2025(en)

## — Gain map

## —

# iT

# eh Standards

# (https://standards.iteh.ai)

# Document Preview

ISO 21496-1:2025

## International

## Standard

## ISO 21496-1

## First edition

## 2025-07

© ISO 2025


---

### https://standards.iteh.ai/catalog/standards/iso/ef1c15f5-fbe6-421d-b145-887655776304/iso-21496-1-2025

© ISO 2025 All rights reserved. Unless otherwise specified, or required in the context of its implementation, no part of this publication may  be reproduced or utilized otherwise in any form or by any means, electronic or mechanical, including photocopying, or posting on  the internet or an intranet, without prior written permission. Permission can be requested from either ISO at the address below  or ISO’s member body in the country of the requester. ISO copyright office CP 401 • Ch. de Blandonnet 8 CH-1214 Vernier, Geneva Phone: +41 22 749 01 11 Email: [copyright@iso.org](mailto:copyright@iso.org) Website: www.iso.org Published in Switzerland

### COPYRIGHT PROTECTED DOCUMENT

# (https://standards.iteh.ai)

### ISO 21496-1:2025(en)

# iT

# eh Standards

# Document Preview

### ISO 21496-1:2025

© ISO 2025 – All rights reserved

**﻿**

ii


---

### Contents

**Foreword..................................................................................................................................................................................................................................................... iv**

**Introduction**

**1 Scope.............................................................................................................................................................................................................................................. 1**

**2**

**3 Terms,**

**4**

**5 Metadata**

**6**  [https://standards.iteh.ai/catalog/standards/iso/ef1c15f5-fbe6-421d-b145-887655776304/iso-21496-1-2025](https://standards.iteh.ai/catalog/standards/iso/ef1c15f5-fbe6-421d-b145-887655776304/iso-21496-1-2025)

**Annex A (informative) Computing the gain map................................................................................................................................................ 8**

**Annex B (normative) Colour conversion.................................................................................................................................................................. 10**

**Annex C (normative) Storing the gain map........................................................................................................................................................... 11**

**Bibliography.......................................................................................................................................................................................................................................... 15**

**Normative references.................................................................................................................................................................................................. 1**

**Gain map requirements............................................................................................................................................................................................. 2** 4.1  4.2  4.3  4.4  4.5 Orientation...............................................................................................................................................................................................................4 5.1  5.2

5.3

**Gain map application.................................................................................................................................................................................................... 6** 6.1  6.2 6.3

.............................................................................................................................................................................................................................................. v

**definitions,**

General.........................................................................................................................................................................................................................2 Gain map dimensions.....................................................................................................................................................................................3 Gain map colour components..................................................................................................................................................................3 Gain map quantization..................................................................................................................................................................................3

.................................................................................................................................................................................................................................... 4 General.........................................................................................................................................................................................................................4 Gain map metadata...........................................................................................................................................................................................4 5.2.1 General......................................................................................................................................................................................................4 5.2.2 Dimensions............................................................................................................................................................................................4 5.2.3 Quantization.........................................................................................................................................................................................4 5.2.4 Number of gain map components.....................................................................................................................................4 5.2.5 Per-component metadata.........................................................................................................................................................4 5.2.6 Baseline high dynamic range headroom....................................................................................................................5 5.2.7 Alternate HDR headroom.........................................................................................................................................................5 5.2.8 Version tag.............................................................................................................................................................................................5 Colorimetry metadata 5.3.1 General......................................................................................................................................................................................................5 5.3.2 Baseline image colorimetry metadata..........................................................................................................................5 5.3.3 Alternate image colorimetry metadata 5.3.4 Gain map application space colour primaries metadata..............................................................................6

General.........................................................................................................................................................................................................................6 Processing the gain map..............................................................................................................................................................................6 6.2.1 Unnormalizing the gain map.................................................................................................................................................6 6.2.2 Resampling the gain map.........................................................................................................................................................7 Applying the gain map...................................................................................................................................................................................7

**andacronyms.................................................................................................................................................................. 1**

# (https://standards.iteh.ai)

**ISO 21496-1:2025(en)**

# iT

# eh Standards

....................................................................................................................................................................................5

# Document Pr

ISO 21496-1:2025

© ISO 2025 – All rights reserved

**﻿**

iii

# eview

.......................................................................................................................

Page 6


---

### Foreword

ISO (the International Organization for Standardization) is a worldwide federation of national standards  bodies (ISO member bodies). The work of preparing International Standards is normally carried out through  ISO technical  has been established  governmental and non-governmental, in liaison with ISO, also take part in the work. ISO collaborates closely  with the International Electrotechnical Commission (IEC) on all matters of electrotechnical standardization.

The procedures used to develop this document and those intended for its further maintenance are described  in the ISO/IEC Directives, Part 1. In particular, the different approval criteria needed for the different types  of ISO document should be noted. This document was drafted in accordance with the editorial rules of the  ISO/IEC Directives, Part 2 (see www.iso.org/directives

ISO draws attention to the possibility that the implementation of this document may involve the use of a  patent. ISO takes no position concerning the evidence, validity or applicability of any claimed patent rights in  respect thereof. As of the date of publication of this document, ISO had received notice of a patent which may  be required to implement this document. However, implementers are cautioned that this may not represent  the latest information, which may be obtained from the patent database available at  ISO shall not be held responsible for identifying any or all such patent rights.

Any trade name used in this document is information given for the convenience of users and does not  constitute an endorsement.

For an explanation of the voluntary nature of standards, the meaning of ISO specific terms and expressions  related to  Organization (WTO) principles in the Technical Barriers to Trade (TBT), see

This document was prepared by Technical Committee ISO/TC 42, Photography.

Any feedback or questions on this document should be directed to the user’s national standards body. A  complete listing of these bodies can be found at www.iso.org/members.html

[https://standards.iteh.ai/catalog/standards/iso/ef1c15f5-fbe6-421d-b145-887655776304/iso-21496-1-2025](https://standards.iteh.ai/catalog/standards/iso/ef1c15f5-fbe6-421d-b145-887655776304/iso-21496-1-2025)

committees.

conformity

Each member body interested  has the right

assessment,

# (https://standards.iteh.ai)

**ISO 21496-1:2025(en)**

to be represented

as well as information

# iT

# eh Standards

# Document Preview

ISO 21496-1:2025

© ISO 2025 – All rights reserved

in a subject for which a technical  on that

).

about

**﻿**

iv

committee.

ISO's adherence

International

|  | users | and | does | not |
|---|---|---|---|---|
|  | terms | and | expressions |  |
|  | to | the World | Trade |  |
|  |  | www.iso.org/iso/foreword.html | | . |

.

committee  organizations,

World Trade www.iso.org/patents.
