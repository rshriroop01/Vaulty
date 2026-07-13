# Vaultly — Product Requirements Document

**Version:** 1.0 · **Status:** Product Requirements Document · **Author:** Shriroop Roychoudhury

> Markdown transcription of the original PRD (`Vaultly-prd.md.pdf`). This file is the single source of truth for product scope.

## 1. Executive Summary

### Overview
Vaultly is a secure cloud platform that helps individuals and families organize every important document in one place while proactively reminding them before important dates.

Instead of searching through Gmail, drawers, Dropbox folders, filing cabinets and old emails, Vaultly automatically imports, categorizes and protects life documents.

Think of Vaultly as **Dropbox + Apple Health + TurboTax Document Vault + Gmail AI**, specifically built for managing your life's paperwork.

### Vision
Become the operating system for household administration.

If a user asks "Where is my passport?" or "When does my insurance expire?" — Vaultly should answer instantly.

### Problem Statement
The average American household stores important documents across multiple locations: Gmail, Google Drive, Dropbox, filing cabinets, photos, Apple Notes, printed copies.

Important deadlines are forgotten. Examples: passport expires, warranty expires, return window missed, insurance auto-renews, medical bill overdue. This costs users time and money.

Vaultly centralizes these documents and prevents expensive mistakes.

## Target Market
- **Primary:** homeowners, families, parents, professionals
- **Secondary:** students, renters, seniors, pet owners
- **Country:** United States first, international later

## Business Model — Freemium SaaS
- **Free:** 100MB storage · 25 documents · OCR on 5 documents/month · basic reminders
- **Premium ($8.99/month):** unlimited OCR · AI assistant · unlimited reminders · Gmail sync · unlimited storage
- **Family ($14.99/month):** up to 6 members · shared vault · shared reminders · emergency access · family dashboard
- **Future revenue:** insurance referrals, extended warranty partnerships, tax software integrations, home service referrals, financial planning integrations

## Success Metrics (Year 1)
| Metric | Target |
|---|---|
| Users | 10,000 |
| Paying users | 500 |
| MRR | $4,500+ |
| OCR accuracy | 95% |
| Search latency | <300ms |
| Upload time | <2 seconds |
| Reminder delivery success | 99% |
| Crash rate | <0.5% |

## Core Principles
1. Never lose an important document.
2. Never miss an important deadline.
3. Find anything within five seconds.
4. Security above everything else.
5. Automation beats manual work.

## Product Pillars
1. **Document Storage** — every important document belongs here.
2. **Organization** — AI automatically categorizes everything.
3. **Reminders** — the app remembers deadlines so users don't have to.
4. **Family Sharing** — trusted people can access important information during emergencies.
5. **AI Assistant** — users should never browse folders again; they simply ask ("Show my Costco receipts", "Which warranties expire next month?").

## Competitive Analysis
| Product | Strength | Weakness |
|---|---|---|
| Dropbox | Storage | No life organization |
| Google Drive | Search | No reminders |
| Evernote | Notes | Poor document workflows |
| Notion | Flexible | Requires manual organization |
| Apple Notes | Simple | Not structured |
| OneDrive | Storage | No OCR intelligence |
| FileThis | Limited integrations | Weak consumer experience |

**Opportunity:** none combine OCR, Gmail import, warranty tracking, medical bills, insurance, AI search, and an emergency binder inside one experience.

## Product Scope

**Version 1:** ✅ Authentication · Dashboard · OCR · Search · Receipt Manager · Warranty Tracking · Insurance Center · Medical Bills · Emergency Binder · AI Search · Email Reminders

**Version 2:** vehicle records, home inventory, tax documents, subscriptions, estate planning, budgeting, mortgage documents, investment statements

**Version 3:** mobile apps, browser extension, Apple Wallet integration, Google Wallet, voice assistant, calendar sync, family timeline

## Design Philosophy
The application should feel professional, calm, minimal, warm, trustworthy — never cluttered. Everything important should be accessible in no more than **3 clicks**.

*(Implemented as the "Ledger" design system — see [design/handoff-v1/README.md](design/handoff-v1/README.md).)*

## User Journey
- **Day 1:** user signs up, imports Gmail; Vaultly automatically detects Amazon receipts, Costco receipts, insurance PDFs, medical bills; dashboard immediately fills with documents.
- **Week 1:** uploads passports, adds insurance, uploads warranties, adds spouse.
- **Month 1:** receives reminder "Home insurance renews in 30 days" → clicks Review Policy → done.
- **Month 6:** needs washing machine warranty → searches "Samsung Washer" → PDF appears instantly.
- **Emergency:** spouse scans Emergency QR → gets access to emergency contacts, medical information, insurance, hospital, blood group, current medications — without needing account credentials.

## Why Users Will Pay
Vaultly saves money, time, and stress. Measurable value: prevent missed warranty claims, avoid insurance lapses, find documents instantly, never lose receipts, organize medical paperwork, prepare for emergencies.

## Product North Star
> **"If it's an important life document, Vaultly should know where it is, when it expires, and who needs access to it."**

## Engineering Principles
- API-first architecture
- Modular services
- Production-ready from day one
- Infrastructure as code
- Secure by default
- Feature flags for new functionality
- Test coverage ≥80%
- Zero hardcoded secrets
- Comprehensive audit logging
