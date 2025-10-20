# Week 5 Update 

- Mentor: Arjun Jain (Slack preferred)
- Advisor: Harshit Joshi; 
- Domain Advisor: Prof. Chieh-Ju Chao
- Team Member: Du Li, Michael Yang
- Project: AI-Powered Heart Failure Medication Assistant (HF-AGENT)

## Summary
- Kicked off project setup and reviewed Genie framework paper and repo.
- Clarified initial scope: medication titration assistance, symptom/risk detection, escalation triggers.

## Progress
- Read core references: 2022 AHA/ACC/HFSA HF guideline; JACC titration review; Genie worksheets paper.

## System design (Initial)
- Modules: dialogue manager, information extraction, risk screen (rules-first), recommendation, escalation, audit.
- Flow: intake → risk screen → recommendation → escalation; red-flags have highest priority.
- Worksheets (Genie): `HF_Intake`, `HF_RiskScreen`, `HF_GDMT_Titration_Reco`, `HF_Escalation`.

## What we plan for next week
- Build a minimal conversational loop (prototype) using Genie worksheets: intake → risk screen → recommendation → escalation.
- Prepare a small synthetic conversation set to test flows; define evaluation rubric (task success, safety checks).


