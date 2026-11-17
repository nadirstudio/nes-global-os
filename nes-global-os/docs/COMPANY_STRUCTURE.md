# Company Structure

Source: audit of the four official websites on 9 Nov 2026 plus the CEO's specification. Contact details below are exactly
as published; nothing was invented. Items marked **(confirm)** need the CEO's input.

## Parent company — NADIR E-SKILLS (SMC-PRIVATE) LIMITED (`NES-GROUP`)

- CEO: Mubshair Ali **(confirm spelling — nesdigitalmarketing.com metadata shows "Mubashir Ali")**
- Head office (per nadireskills.com): Plot # 16, Fantom Mall, I-8 Markaz, Islamabad, 44790 · 03400 524444 · info@nadireskills.com · WhatsApp +92 341 7749005
- Positioning: "One Ecosystem. Multiple Possibilities. Shared Growth." — skills training, study abroad, websites/branding, marketing and events under one roof.
- Customer journey (site): pick a category / message on WhatsApp → routed to the right partner team → scope, responsibilities and timeline agreed before work starts.
- Group-wide departments in the system: Executive Office, Human Resources, Finance, Operations, Information Technology, Legal & Compliance.

## Business units

| Code | Unit | Published details | Departments in the system | Sales pipeline stages |
|---|---|---|---|---|
| NES-CONS | **NES Consultancy** | consultant.nadireskills.com · Ward No. 5, Mandi Bahauddin · 0345 2193466 (WhatsApp) · Study destinations UK, USA, Canada, Australia, Cyprus, France, New Zealand, Italy (+others) · Services: university admissions, student visa & interview, IELTS/PTE prep (Alfa IELTS/PTE portals), visa processing, migration & overseas jobs, translation, NTN registration, tax returns, tax planning, SECP company formation, trademark, Chamber of Commerce, file preparation | Sales & Client Services · Study Abroad & Admissions · Visa, Migration & Jobs · Embassy Appointment Booking · Business & Tax Services · Operations & Quality | Inquiry → Needs Assessment → Evaluate & Prepare → Submit & Track → Welcome / Next Steps (the site's own N-E-S-W "compass" steps) |
| NES-ACAD | **Nadir Academy** | academy.nadireskills.com · academy@nadireskills.com · +92 345 2193460 · Ward No. 5, Mandi Bahauddin · Mon–Sat 10–6 · Courses: Graphic Designing, E-Commerce, Digital Marketing, Basic IT, Arduino, Programming, IELTS/PTE · Admissions via Google Form · online result & verification pages · Store (hardware, software, books) | Sales and Admissions · Academic Management · Administration · Examination | Inquiry → Counselling → Admission Form → Fee Pending → Enrolled |
| NES-DM | **NES Digital Marketing** | nesdigitalmarketing.com · digitalmarketingnes@gmail.com · WhatsApp +92 333 8208609 · Pakistan & international clients · SEO, Meta Ads, Google Ads, Social Media, Website Design & Development, Lead Generation, Content, CRO, Sales Funnels, Strategy · 5-step process: Discover, Strategize, Build & Launch, Measure, Scale | Sales · Creative · Development · E-commerce | Inquiry → Free Consultation → Proposal Sent → Negotiation → Onboarding |
| NES-SERV | **Nadir Services** | Government documents, attestation, translation and admissions support (nadireskills.com/services) · Printing, online applications, computer services (from brief) | Service Desk | Request → Documents Received → In Process → Ready for Collection |
| NES-STUDIO | **Nadir Studio** | Logos, branding and printing. Only web presence is a Facebook video page **(confirm address/contacts)** | Creative & Production | Order → Design → Client Approval → Production → Ready |
| NES-EVENTS | **NES Events** | Published as "Nadir Expo & Events": study-abroad expos, educational fairs, business & trade exhibitions, seminars, sponsorship. Its site link currently points to the About page. | Events & Expos | Inquiry → Proposal → Confirmed → Executed |
| NES-ECOM | **NES E-commerce** | Listed in the brief; no public page found **(confirm scope — e.g. own Shopify stores)** | E-commerce Operations | Inquiry → Quote → Order Placed |

## Observations from the audit (for the CEO)

1. **Partner brands not in the brief:** nadireskills.com also lists **Eye Cue Copy** (copywriting) and **Income Line**
   (content/monetisation). They were *not* added to the system. Add them via Organisation → "+ Company / venture" if they are group units.
2. **Academy website still contains template placeholder text** ("There are many variations words passages…", a default
   "Hello world!" blog post, empty "Read More" links). Worth fixing — it affects trust and SEO.
3. **Four different WhatsApp numbers** are published (group, consultancy, academy, digital marketing). The WhatsApp module
   (Phase 12) is designed for exactly this: one inbox, company-wise numbers, department routing.
4. **Two locations:** Islamabad (group office) and Mandi Bahauddin (consultancy, academy). Locations can be added as
   projects/ventures; a dedicated "branches" entity is in the Phase 10 backlog.
5. NES Studio and NES Events lack their own web pages — both rely on WhatsApp/Facebook.

## How structure changes are made

- New company / venture: Organisation → "+ Company / venture" (CEO). A default sales pipeline is created.
- New department: Organisation → "+ Department" (CEO/Directors). Then create its AI coordinator in the Agent Factory.
- Department head: edit the department (API `PATCH /api/departments/{id}`) or set via the person's profile.
- All changes are audit-logged.
