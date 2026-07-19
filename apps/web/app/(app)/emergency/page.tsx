"use client";

/** Emergency binder — screen 2h: contents checklist, navy QR card with
 *  issue/print/revoke + PIN, delegates, and the access log. The raw QR token
 *  exists only right after issue — reissue to get a new printable code. */

import { useCallback, useEffect, useState } from "react";
import QRCode from "qrcode";
import {
  getBinder,
  issueQr,
  revokeQr,
  updateBinder,
  type Binder,
  type Contact,
  type Delegate,
  type MedicalInfo,
} from "@/lib/family";

function fmt(at: string): string {
  return new Date(at).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export default function EmergencyPage() {
  const [binder, setBinder] = useState<Binder | null>(null);
  const [qrDataUrl, setQrDataUrl] = useState<string | null>(null);
  const [pin, setPin] = useState("");
  const [editing, setEditing] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setBinder(await getBinder().catch(() => null));
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function onIssue() {
    if (!/^\d{4,8}$/.test(pin)) {
      setNote("PIN must be 4–8 digits.");
      return;
    }
    setNote(null);
    const issued = await issueQr(pin);
    const url = `${window.location.origin}/e/${issued.token}`;
    setQrDataUrl(await QRCode.toDataURL(url, { width: 300, margin: 1 }));
    setPin("");
    void refresh();
  }

  async function onRevoke() {
    await revokeQr();
    setQrDataUrl(null);
    setNote("QR revoked. Old printed codes no longer work.");
    void refresh();
  }

  function printQr() {
    if (!qrDataUrl) return;
    const w = window.open("", "_blank");
    if (!w) return;
    w.document.write(
      `<html><head><title>Vaultly Emergency QR</title></head>
       <body style="font-family:sans-serif;text-align:center;padding:40px">
         <h2>Vaultly emergency access</h2>
         <img src="${qrDataUrl}" width="300" height="300"/>
         <p>Scan + enter the family PIN.<br/>Wallet, fridge, glovebox.</p>
         <script>window.print()</script>
       </body></html>`,
    );
  }

  return (
    <>
      <h1 className="mb-0.5 text-[21px] font-semibold tracking-[-0.01em]">Emergency binder</h1>
      <p className="mb-5 text-[13px] text-text-sub">
        Critical documents your family can reach in a crisis — even without your password.
      </p>
      {note && (
        <div className="mb-3 rounded-tag bg-warn-bg px-3 py-2 text-[12px] font-medium text-warn">
          {note}
        </div>
      )}

      <div className="grid grid-cols-3 items-start gap-4">
        {/* Column 1: checklist + editor */}
        <div className="grid gap-4">
          <div className="rounded-[10px] border border-border bg-card px-[18px] py-4">
            <div className="mb-2.5 flex items-baseline justify-between">
              <span className="text-[14px] font-semibold">Binder contents</span>
              <span className="text-[11.5px] text-text-faint">
                {binder
                  ? `${binder.checklist.filter((i) => i.done).length} of ${binder.checklist.length} complete`
                  : "…"}
              </span>
            </div>
            {(binder?.checklist ?? []).map((item) => (
              <div
                key={item.key}
                className="flex items-center gap-[11px] border-t border-[#f2f4f6] py-[9px]"
              >
                <span
                  className={`grid h-5 w-5 flex-none place-items-center rounded-[6px] text-[11px] font-bold ${
                    item.done ? "bg-ok-bg text-ok" : "bg-urgent-bg text-urgent"
                  }`}
                >
                  {item.done ? "✓" : "＋"}
                </span>
                <div>
                  <div className="text-[13px] font-medium">{item.label}</div>
                  <div className={`text-[11px] ${item.done ? "text-ok" : "text-urgent"}`}>
                    {item.sub}
                  </div>
                </div>
              </div>
            ))}
            <button
              onClick={() => setEditing((v) => !v)}
              className="mt-3 w-full rounded-control border border-input-border py-2 text-[12.5px] font-semibold text-ink hover:bg-app"
            >
              {editing ? "Close editor" : "Edit contacts & medical info"}
            </button>
          </div>
          {editing && binder && (
            <BinderEditor
              binder={binder}
              onSaved={() => {
                setEditing(false);
                void refresh();
              }}
            />
          )}
        </div>

        {/* Column 2: navy QR card */}
        <div className="rounded-[10px] bg-ink p-5 text-center text-white">
          <div className="mb-1 text-[14px] font-semibold">Emergency QR</div>
          <div className="mb-4 text-[12px] text-[#b9c6d3]">Print it. Wallet, fridge, glovebox.</div>
          {qrDataUrl ? (
            <>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={qrDataUrl}
                alt="Emergency QR code"
                className="mx-auto h-[150px] w-[150px] rounded-[10px] bg-white p-1.5"
              />
              <div className="mt-3 flex justify-center gap-2.5">
                <button
                  onClick={printQr}
                  className="rounded-[6px] bg-white/14 px-3 py-1.5 text-[12px] font-semibold"
                >
                  Print
                </button>
                <button
                  onClick={() => void onRevoke()}
                  className="rounded-[6px] bg-white/14 px-3 py-1.5 text-[12px] font-semibold"
                >
                  Revoke
                </button>
              </div>
              <div className="mt-3 text-[11px] text-[#7fa8cc]">
                This code is shown once — print it now.
              </div>
            </>
          ) : binder?.qr_active ? (
            <>
              <div className="mx-auto grid h-[150px] w-[150px] place-items-center rounded-[10px] bg-white/10 text-[12px] text-[#b9c6d3]">
                QR active
                {binder.qr_issued_at ? (
                  <span className="px-4 text-[10.5px]">issued {fmt(binder.qr_issued_at)}</span>
                ) : null}
              </div>
              <div className="mt-3 flex justify-center gap-2.5">
                <button
                  onClick={() => void onRevoke()}
                  className="rounded-[6px] bg-white/14 px-3 py-1.5 text-[12px] font-semibold"
                >
                  Revoke
                </button>
              </div>
              <div className="mt-3 text-[11px] text-[#7fa8cc]">
                Need a new printout? Revoke, then issue a fresh QR below.
              </div>
            </>
          ) : (
            <div className="mx-auto grid h-[150px] w-[150px] place-items-center rounded-[10px] bg-white/10 text-[12px] text-[#b9c6d3]">
              No QR issued yet
            </div>
          )}
          <div className="mt-4 border-t border-white/15 pt-3.5">
            <label htmlFor="pin" className="mb-1.5 block text-[11.5px] text-[#b9c6d3]">
              {binder?.qr_active ? "Reissue with a new PIN" : "Set a family PIN to issue"}
            </label>
            <div className="flex justify-center gap-2">
              <input
                id="pin"
                value={pin}
                onChange={(e) => setPin(e.target.value)}
                inputMode="numeric"
                placeholder="4–8 digits"
                className="w-28 rounded-control border border-white/25 bg-white/10 px-3 py-1.5 text-center font-mono text-[13px] text-white outline-none placeholder:text-white/40"
              />
              <button
                onClick={() => void onIssue()}
                className="rounded-control bg-white px-3.5 py-1.5 text-[12px] font-semibold text-ink"
              >
                {binder?.qr_active ? "Reissue" : "Issue QR"}
              </button>
            </div>
            <div className="mt-2 text-[10.5px] text-[#7fa8cc]">
              Every scan notifies you and is written to the audit log.
            </div>
          </div>
        </div>

        {/* Column 3: delegates + access log */}
        <div className="grid gap-4">
          <div className="rounded-[10px] border border-border bg-card px-[18px] py-4">
            <div className="mb-2.5 text-[14px] font-semibold">Delegates</div>
            {(binder?.delegates ?? []).length === 0 ? (
              <div className="rounded-control border border-dashed border-border px-4 py-5 text-center text-[12px] text-text-sub">
                Add who holds the QR + PIN in the editor.
              </div>
            ) : (
              (binder?.delegates ?? []).map((d, i) => (
                <div
                  key={`${d.name}-${i}`}
                  className="flex items-center gap-2.5 border-t border-[#f2f4f6] py-2 first:border-t-0"
                >
                  <div className="grid h-7 w-7 flex-none place-items-center rounded-full bg-avatar text-[10px] font-semibold text-ink">
                    {d.name
                      .split(" ")
                      .map((p) => p[0])
                      .slice(0, 2)
                      .join("")
                      .toUpperCase()}
                  </div>
                  <div>
                    <div className="text-[13px] font-medium">{d.name}</div>
                    <div className="text-[11.5px] text-text-sub">{d.relation}</div>
                  </div>
                </div>
              ))
            )}
          </div>

          <div className="rounded-[10px] border border-border bg-card px-[18px] py-4">
            <div className="mb-2.5 text-[14px] font-semibold">Access log</div>
            {(binder?.access_log ?? []).length === 0 ? (
              <div className="rounded-control border border-dashed border-border px-4 py-5 text-center text-[12px] text-text-sub">
                No access yet — scans appear here with time and result.
              </div>
            ) : (
              (binder?.access_log ?? []).map((entry, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between border-t border-[#f2f4f6] py-2 text-[12.5px] first:border-t-0"
                >
                  <span className={entry.action === "emergency.scan" ? "text-text" : "text-urgent"}>
                    {entry.action === "emergency.scan" ? "Binder accessed" : "Wrong PIN attempt"}
                  </span>
                  <span className="font-mono text-[11.5px] text-text-faint">{fmt(entry.at)}</span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </>
  );
}

function BinderEditor({ binder, onSaved }: { binder: Binder; onSaved: () => void }) {
  const [contacts, setContacts] = useState<Contact[]>(
    binder.contacts.length ? binder.contacts : [{ name: "", phone: "", relation: "" }],
  );
  const [medical, setMedical] = useState<MedicalInfo>(binder.medical);
  const [delegates, setDelegates] = useState<Delegate[]>(
    binder.delegates.length ? binder.delegates : [{ name: "", relation: "" }],
  );

  const input =
    "w-full rounded-control border border-input-border px-2.5 py-[7px] text-[12.5px] outline-none focus:border-ink";

  return (
    <div className="rounded-[10px] border border-border bg-card px-[18px] py-4">
      <div className="mb-2 text-[13px] font-semibold">Emergency contacts</div>
      {contacts.map((c, i) => (
        <div key={i} className="mb-2 grid grid-cols-3 gap-2">
          <input
            className={input}
            placeholder="Name"
            value={c.name}
            onChange={(e) =>
              setContacts(contacts.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))
            }
          />
          <input
            className={input}
            placeholder="Phone"
            value={c.phone}
            onChange={(e) =>
              setContacts(contacts.map((x, j) => (j === i ? { ...x, phone: e.target.value } : x)))
            }
          />
          <input
            className={input}
            placeholder="Relation"
            value={c.relation}
            onChange={(e) =>
              setContacts(
                contacts.map((x, j) => (j === i ? { ...x, relation: e.target.value } : x)),
              )
            }
          />
        </div>
      ))}
      <div className="mb-3 mt-2 text-[13px] font-semibold">Medical information</div>
      <div className="grid grid-cols-2 gap-2">
        <input
          className={input}
          placeholder="Blood group (e.g. B+)"
          value={medical.blood_group ?? ""}
          onChange={(e) => setMedical({ ...medical, blood_group: e.target.value })}
        />
        <input
          className={input}
          placeholder="Preferred hospital"
          value={medical.hospital ?? ""}
          onChange={(e) => setMedical({ ...medical, hospital: e.target.value })}
        />
        <input
          className={input}
          placeholder="Allergies"
          value={medical.allergies ?? ""}
          onChange={(e) => setMedical({ ...medical, allergies: e.target.value })}
        />
        <input
          className={input}
          placeholder="Current medications"
          value={medical.medications ?? ""}
          onChange={(e) => setMedical({ ...medical, medications: e.target.value })}
        />
      </div>
      <div className="mb-2 mt-3 text-[13px] font-semibold">Delegates</div>
      {delegates.map((d, i) => (
        <div key={i} className="mb-2 grid grid-cols-2 gap-2">
          <input
            className={input}
            placeholder="Name"
            value={d.name}
            onChange={(e) =>
              setDelegates(delegates.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))
            }
          />
          <input
            className={input}
            placeholder="Relation"
            value={d.relation}
            onChange={(e) =>
              setDelegates(
                delegates.map((x, j) => (j === i ? { ...x, relation: e.target.value } : x)),
              )
            }
          />
        </div>
      ))}
      <button
        onClick={async () => {
          await updateBinder({
            contacts: contacts.filter((c) => c.name),
            medical,
            delegates: delegates.filter((d) => d.name),
          });
          onSaved();
        }}
        className="mt-2 w-full rounded-control bg-ink py-2 text-[12.5px] font-semibold text-white"
      >
        Save binder
      </button>
    </div>
  );
}
