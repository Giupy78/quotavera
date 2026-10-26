/**
 * Il paese di un campionato, nella forma che vuole schema.org.
 *
 * `addressCountry` si aspetta un codice ISO 3166-1 alpha-2, non il nome in
 * italiano che usiamo in pagina. La mappa sta qui e non in `catalogo.py`
 * perché serve a una cosa sola — i dati strutturati — e aggiungere un campo al
 * catalogo vorrebbe dire rigenerare tutti i file del sito per due lettere.
 *
 * **Inghilterra e Scozia hanno lo stesso codice**, `GB`, ed è corretto: un
 * indirizzo postale scozzese è un indirizzo del Regno Unito. La distinzione
 * non si perde, la porta `addressRegion`, che è il campo giusto per dirla.
 */
type Paese = { iso: string; regione?: string };

const PAESI: Record<string, Paese> = {
  Italia: { iso: 'IT' },
  Inghilterra: { iso: 'GB', regione: 'England' },
  Scozia: { iso: 'GB', regione: 'Scotland' },
  Spagna: { iso: 'ES' },
  Germania: { iso: 'DE' },
  Francia: { iso: 'FR' },
  'Paesi Bassi': { iso: 'NL' },
  Portogallo: { iso: 'PT' },
  Turchia: { iso: 'TR' },
  Belgio: { iso: 'BE' },
  Grecia: { iso: 'GR' },
};

/**
 * L'indirizzo di una partita di campionato. Il paese lo sappiamo sempre — è
 * quello della competizione, e una partita casalinga si gioca lì — la città
 * solo quando ESPN ci ha dato lo stadio.
 *
 * Restituisce sempre un oggetto: `location` senza `address` è il secondo dei
 * due avvisi arrivati da Search Console il 26 ottobre 2026, e un campo che
 * manca è peggio di uno meno preciso del massimo.
 */
export function indirizzo(paese: string | undefined, citta?: string | null) {
  const p = paese ? PAESI[paese] : undefined;
  return {
    '@type': 'PostalAddress',
    ...(citta ? { addressLocality: citta } : {}),
    ...(p?.regione ? { addressRegion: p.regione } : {}),
    ...(p ? { addressCountry: p.iso } : {}),
  };
}
