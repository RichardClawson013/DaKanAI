"""Rondetelling en noodrem — port van BedrijfspandAI interviewStatus.js"""

RONDE_WAARSCHUWING = 8
RONDE_DESTILLATIE = 10
RONDE_AFSLUITEN = 12
NOODREM_TOTAAL = 2500

EXTRACTIE_RESET_TYPEN = {"taak", "edge"}

WAARSCHUWINGSTEKST = (
    "We naderen een grens in dit onderdeel van het gesprek. Wil je je antwoord "
    "nog aanscherpen — bijvoorbeeld door het eerst voor jezelf op een rijtje te "
    "zetten — voordat we verdergaan?"
)

AFSLUITTEKST = (
    "Dankjewel voor alle informatie. We gaan ons best doen om wat nu nog mist "
    "in te vullen op een manier die waarde toevoegt aan jouw verhaal en bedrijf."
)


def rondes_sinds_laatste_extractie(transcript):
    rondes = 0
    for beurt in transcript:
        if beurt.get("type") == "naamstap" or beurt.get("type") in EXTRACTIE_RESET_TYPEN:
            rondes = 0
            continue
        if beurt.get("type") == "dialoog" and beurt.get("spreker") == "interviewer":
            rondes += 1
    return rondes


def noodrem_bereikt(transcript):
    return len(transcript) >= NOODREM_TOTAAL


def bepaal_vraag_status(transcript):
    if noodrem_bereikt(transcript):
        return "noodrem"
    rondes = rondes_sinds_laatste_extractie(transcript)
    if rondes >= RONDE_AFSLUITEN:
        return "afsluiten"
    if rondes >= RONDE_DESTILLATIE:
        return "destilleren"
    if rondes >= RONDE_WAARSCHUWING:
        return "waarschuwing"
    return "normaal"
