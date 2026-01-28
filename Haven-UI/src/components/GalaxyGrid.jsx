import React, { useEffect, useState, useMemo } from 'react'
import axios from 'axios'
import Card from './Card'
import { SparklesIcon, MapIcon, ArrowPathIcon, GlobeAltIcon } from '@heroicons/react/24/outline'

// Complete galaxy data - all 256 galaxies from No Man's Sky
const ALL_GALAXIES = {
  'Euclid': { num: 1, type: 'norm', desc: 'The starting galaxy - most explored' },
  'Hilbert Dimension': { num: 2, type: 'norm', desc: 'Second galaxy reached via center' },
  'Calypso': { num: 3, type: 'harsh', desc: 'Raging Galaxy - high conflict' },
  'Hesperius Dimension': { num: 4, type: 'norm', desc: 'Fourth galaxy' },
  'Hyades': { num: 5, type: 'norm', desc: 'Fifth galaxy' },
  'Ickjamatew': { num: 6, type: 'norm', desc: 'Sixth galaxy' },
  'Budullangr': { num: 7, type: 'lush', desc: 'Ancestral Galaxy - more lush planets' },
  'Kikolgallr': { num: 8, type: 'norm', desc: 'Eighth galaxy' },
  'Eltiensleen': { num: 9, type: 'norm', desc: 'Ninth galaxy' },
  'Eissentam': { num: 10, type: 'lush', desc: 'Tranquil Galaxy - paradise planets' },
  'Elkupalos': { num: 11, type: 'norm', desc: 'Eleventh galaxy' },
  'Aptarkaba': { num: 12, type: 'norm', desc: 'Twelfth galaxy' },
  'Ontiniangp': { num: 13, type: 'norm', desc: 'Thirteenth galaxy' },
  'Odiwagiri': { num: 14, type: 'norm', desc: 'Fourteenth galaxy' },
  'Ogtialabi': { num: 15, type: 'norm', desc: 'Fifteenth galaxy' },
  'Muhacksonto': { num: 16, type: 'norm', desc: 'Sixteenth galaxy' },
  'Hitonskyer': { num: 17, type: 'norm', desc: 'Seventeenth galaxy' },
  'Rerasmutul': { num: 18, type: 'norm', desc: 'Eighteenth galaxy' },
  'Isdoraijung': { num: 19, type: 'lush', desc: 'Halcyon Galaxy - more lush planets' },
  'Doctinawyra': { num: 20, type: 'norm', desc: 'Twentieth galaxy' },
  'Loychazinq': { num: 21, type: 'norm', desc: 'Twenty-first galaxy' },
  'Zukasizawa': { num: 22, type: 'norm', desc: 'Twenty-second galaxy' },
  'Ekwathore': { num: 23, type: 'norm', desc: 'Twenty-third galaxy' },
  'Yeberhahne': { num: 24, type: 'norm', desc: 'Twenty-fourth galaxy' },
  'Twerbetek': { num: 25, type: 'norm', desc: 'Twenty-fifth galaxy' },
  'Sivarates': { num: 26, type: 'norm', desc: 'Twenty-sixth galaxy' },
  'Eajerandal': { num: 27, type: 'norm', desc: 'Twenty-seventh galaxy' },
  'Aldukesci': { num: 28, type: 'norm', desc: 'Twenty-eighth galaxy' },
  'Wotyarogii': { num: 29, type: 'norm', desc: 'Twenty-ninth galaxy' },
  'Sudzerbal': { num: 30, type: 'norm', desc: 'Thirtieth galaxy' },
  'Maupenzhay': { num: 31, type: 'norm', desc: 'Thirty-first galaxy' },
  'Sugueziume': { num: 32, type: 'norm', desc: 'Thirty-second galaxy' },
  'Brogoweldian': { num: 33, type: 'norm', desc: 'Thirty-third galaxy' },
  'Ehbogdenbu': { num: 34, type: 'norm', desc: 'Thirty-fourth galaxy' },
  'Ijsenufryos': { num: 35, type: 'norm', desc: 'Thirty-fifth galaxy' },
  'Nipikulha': { num: 36, type: 'norm', desc: 'Thirty-sixth galaxy' },
  'Autsurabin': { num: 37, type: 'norm', desc: 'Thirty-seventh galaxy' },
  'Lusontrygiamh': { num: 38, type: 'norm', desc: 'Thirty-eighth galaxy' },
  'Rewmanawa': { num: 39, type: 'norm', desc: 'Thirty-ninth galaxy' },
  'Ethiophodhe': { num: 40, type: 'norm', desc: 'Fortieth galaxy' },
  'Urastrykle': { num: 41, type: 'norm', desc: 'Forty-first galaxy' },
  'Xobeurindj': { num: 42, type: 'norm', desc: 'Forty-second galaxy' },
  'Oniijialdu': { num: 43, type: 'norm', desc: 'Forty-third galaxy' },
  'Wucetosucc': { num: 44, type: 'norm', desc: 'Forty-fourth galaxy' },
  'Ebyeloof': { num: 45, type: 'norm', desc: 'Forty-fifth galaxy' },
  'Odyavanta': { num: 46, type: 'norm', desc: 'Forty-sixth galaxy' },
  'Milekistri': { num: 47, type: 'norm', desc: 'Forty-seventh galaxy' },
  'Waferganh': { num: 48, type: 'norm', desc: 'Forty-eighth galaxy' },
  'Agnusopwit': { num: 49, type: 'norm', desc: 'Forty-ninth galaxy' },
  'Teyaypilny': { num: 50, type: 'norm', desc: 'Fiftieth galaxy' },
  'Zalienkosm': { num: 51, type: 'norm', desc: 'Fifty-first galaxy' },
  'Ladgudiraf': { num: 52, type: 'norm', desc: 'Fifty-second galaxy' },
  'Mushonponte': { num: 53, type: 'norm', desc: 'Fifty-third galaxy' },
  'Amsentisz': { num: 54, type: 'norm', desc: 'Fifty-fourth galaxy' },
  'Fladiselm': { num: 55, type: 'norm', desc: 'Fifty-fifth galaxy' },
  'Laanawemb': { num: 56, type: 'norm', desc: 'Fifty-sixth galaxy' },
  'Ilkerloor': { num: 57, type: 'norm', desc: 'Fifty-seventh galaxy' },
  'Davanossi': { num: 58, type: 'norm', desc: 'Fifty-eighth galaxy' },
  'Ploehrliou': { num: 59, type: 'norm', desc: 'Fifty-ninth galaxy' },
  'Corpinyaya': { num: 60, type: 'norm', desc: 'Sixtieth galaxy' },
  'Leckandmeram': { num: 61, type: 'norm', desc: 'Sixty-first galaxy' },
  'Quulngais': { num: 62, type: 'norm', desc: 'Sixty-second galaxy' },
  'Nokokipsechl': { num: 63, type: 'norm', desc: 'Sixty-third galaxy' },
  'Rinblodesa': { num: 64, type: 'norm', desc: 'Sixty-fourth galaxy' },
  'Loydporpen': { num: 65, type: 'norm', desc: 'Sixty-fifth galaxy' },
  'Ibtrevskip': { num: 66, type: 'norm', desc: 'Sixty-sixth galaxy' },
  'Elkowaldb': { num: 67, type: 'norm', desc: 'Sixty-seventh galaxy' },
  'Heholhofsko': { num: 68, type: 'norm', desc: 'Sixty-eighth galaxy' },
  'Yebrilowisod': { num: 69, type: 'norm', desc: 'Sixty-ninth galaxy' },
  'Husalvangewi': { num: 70, type: 'norm', desc: 'Seventieth galaxy' },
  "Ovna'uesed": { num: 71, type: 'norm', desc: 'Seventy-first galaxy' },
  'Bahibusey': { num: 72, type: 'norm', desc: 'Seventy-second galaxy' },
  'Nuybeliaure': { num: 73, type: 'norm', desc: 'Seventy-third galaxy' },
  'Doshawchuc': { num: 74, type: 'norm', desc: 'Seventy-fourth galaxy' },
  'Ruckinarkh': { num: 75, type: 'norm', desc: 'Seventy-fifth galaxy' },
  'Thorettac': { num: 76, type: 'norm', desc: 'Seventy-sixth galaxy' },
  'Nuponoparau': { num: 77, type: 'norm', desc: 'Seventy-seventh galaxy' },
  'Moglaschil': { num: 78, type: 'norm', desc: 'Seventy-eighth galaxy' },
  'Uiweupose': { num: 79, type: 'norm', desc: 'Seventy-ninth galaxy' },
  'Nasmilete': { num: 80, type: 'norm', desc: 'Eightieth galaxy' },
  'Ekdaluskin': { num: 81, type: 'norm', desc: 'Eighty-first galaxy' },
  'Hakapanasy': { num: 82, type: 'norm', desc: 'Eighty-second galaxy' },
  'Dimonimba': { num: 83, type: 'norm', desc: 'Eighty-third galaxy' },
  'Cajaccari': { num: 84, type: 'norm', desc: 'Eighty-fourth galaxy' },
  'Olonerovo': { num: 85, type: 'norm', desc: 'Eighty-fifth galaxy' },
  'Umlanswick': { num: 86, type: 'norm', desc: 'Eighty-sixth galaxy' },
  'Henayliszm': { num: 87, type: 'norm', desc: 'Eighty-seventh galaxy' },
  'Utzenmate': { num: 88, type: 'norm', desc: 'Eighty-eighth galaxy' },
  'Umirpaiya': { num: 89, type: 'norm', desc: 'Eighty-ninth galaxy' },
  'Paholiang': { num: 90, type: 'norm', desc: 'Ninetieth galaxy' },
  'Iaereznika': { num: 91, type: 'norm', desc: 'Ninety-first galaxy' },
  'Yudukagath': { num: 92, type: 'norm', desc: 'Ninety-second galaxy' },
  'Boealalosnj': { num: 93, type: 'norm', desc: 'Ninety-third galaxy' },
  'Yaevarcko': { num: 94, type: 'norm', desc: 'Ninety-fourth galaxy' },
  'Coellosipp': { num: 95, type: 'norm', desc: 'Ninety-fifth galaxy' },
  'Wayndohalou': { num: 96, type: 'norm', desc: 'Ninety-sixth galaxy' },
  'Smoduraykl': { num: 97, type: 'norm', desc: 'Ninety-seventh galaxy' },
  'Apmaneessu': { num: 98, type: 'norm', desc: 'Ninety-eighth galaxy' },
  'Hicanpaav': { num: 99, type: 'norm', desc: 'Ninety-ninth galaxy' },
  'Akvasanta': { num: 100, type: 'norm', desc: 'One hundredth galaxy' },
  // Galaxies 101-256
  'Tuychelisaor': { num: 101, type: 'norm', desc: 'Galaxy #101' },
  'Rivskimbe': { num: 102, type: 'norm', desc: 'Galaxy #102' },
  'Daksanquix': { num: 103, type: 'norm', desc: 'Galaxy #103' },
  'Kissonlin': { num: 104, type: 'norm', desc: 'Galaxy #104' },
  'Aediabiel': { num: 105, type: 'norm', desc: 'Galaxy #105' },
  'Ulosaginyik': { num: 106, type: 'norm', desc: 'Galaxy #106' },
  'Roclaytonycar': { num: 107, type: 'norm', desc: 'Galaxy #107' },
  'Kichiaroa': { num: 108, type: 'norm', desc: 'Galaxy #108' },
  'Irceauffey': { num: 109, type: 'norm', desc: 'Galaxy #109' },
  'Nudquathsenfe': { num: 110, type: 'norm', desc: 'Galaxy #110' },
  'Getaizakaal': { num: 111, type: 'norm', desc: 'Galaxy #111' },
  'Hansolmien': { num: 112, type: 'norm', desc: 'Galaxy #112' },
  'Bloytisagra': { num: 113, type: 'norm', desc: 'Galaxy #113' },
  'Ladsenlay': { num: 114, type: 'norm', desc: 'Galaxy #114' },
  'Luyugoslasr': { num: 115, type: 'norm', desc: 'Galaxy #115' },
  'Ubredhatk': { num: 116, type: 'norm', desc: 'Galaxy #116' },
  'Cidoniana': { num: 117, type: 'norm', desc: 'Galaxy #117' },
  'Jasinessa': { num: 118, type: 'norm', desc: 'Galaxy #118' },
  'Torweierf': { num: 119, type: 'norm', desc: 'Galaxy #119' },
  'Saffneckm': { num: 120, type: 'norm', desc: 'Galaxy #120' },
  'Thnistner': { num: 121, type: 'norm', desc: 'Galaxy #121' },
  'Dotusingg': { num: 122, type: 'norm', desc: 'Galaxy #122' },
  'Luleukous': { num: 123, type: 'norm', desc: 'Galaxy #123' },
  'Jelmandan': { num: 124, type: 'norm', desc: 'Galaxy #124' },
  'Otimanaso': { num: 125, type: 'norm', desc: 'Galaxy #125' },
  'Enjaxusanto': { num: 126, type: 'norm', desc: 'Galaxy #126' },
  'Sezviktorew': { num: 127, type: 'norm', desc: 'Galaxy #127' },
  'Zikehpm': { num: 128, type: 'norm', desc: 'Galaxy #128' },
  'Bephembah': { num: 129, type: 'norm', desc: 'Galaxy #129' },
  'Broomerrai': { num: 130, type: 'norm', desc: 'Galaxy #130' },
  'Meximicka': { num: 131, type: 'norm', desc: 'Galaxy #131' },
  'Venessika': { num: 132, type: 'norm', desc: 'Galaxy #132' },
  'Gaiteseling': { num: 133, type: 'norm', desc: 'Galaxy #133' },
  'Zosakasiro': { num: 134, type: 'norm', desc: 'Galaxy #134' },
  'Drajayanes': { num: 135, type: 'norm', desc: 'Galaxy #135' },
  'Ooibekuar': { num: 136, type: 'norm', desc: 'Galaxy #136' },
  'Urckiansi': { num: 137, type: 'norm', desc: 'Galaxy #137' },
  'Dozivadido': { num: 138, type: 'norm', desc: 'Galaxy #138' },
  'Emiekereks': { num: 139, type: 'norm', desc: 'Galaxy #139' },
  'Meykinunukur': { num: 140, type: 'norm', desc: 'Galaxy #140' },
  'Kimycuristh': { num: 141, type: 'norm', desc: 'Galaxy #141' },
  'Roansfien': { num: 142, type: 'norm', desc: 'Galaxy #142' },
  'Isgarmeso': { num: 143, type: 'norm', desc: 'Galaxy #143' },
  'Daitibeli': { num: 144, type: 'norm', desc: 'Galaxy #144' },
  'Gucuttarik': { num: 145, type: 'norm', desc: 'Galaxy #145' },
  'Enlaythie': { num: 146, type: 'norm', desc: 'Galaxy #146' },
  'Drewweste': { num: 147, type: 'norm', desc: 'Galaxy #147' },
  'Akbulkabi': { num: 148, type: 'norm', desc: 'Galaxy #148' },
  'Homskiw': { num: 149, type: 'norm', desc: 'Galaxy #149' },
  'Zavainlani': { num: 150, type: 'norm', desc: 'Galaxy #150' },
  'Jewijkmas': { num: 151, type: 'norm', desc: 'Galaxy #151' },
  'Itlhotagra': { num: 152, type: 'norm', desc: 'Galaxy #152' },
  'Podalicess': { num: 153, type: 'norm', desc: 'Galaxy #153' },
  'Hiviusauer': { num: 154, type: 'norm', desc: 'Galaxy #154' },
  'Halsebenk': { num: 155, type: 'norm', desc: 'Galaxy #155' },
  'Puikitoac': { num: 156, type: 'norm', desc: 'Galaxy #156' },
  'Gaybakuaria': { num: 157, type: 'norm', desc: 'Galaxy #157' },
  'Grbodubhe': { num: 158, type: 'norm', desc: 'Galaxy #158' },
  'Rycempler': { num: 159, type: 'norm', desc: 'Galaxy #159' },
  'Indjalala': { num: 160, type: 'norm', desc: 'Galaxy #160' },
  'Fontenikk': { num: 161, type: 'norm', desc: 'Galaxy #161' },
  'Pasycihelwhee': { num: 162, type: 'norm', desc: 'Galaxy #162' },
  'Ikbaksmit': { num: 163, type: 'norm', desc: 'Galaxy #163' },
  'Telicianses': { num: 164, type: 'norm', desc: 'Galaxy #164' },
  'Oyleyzhan': { num: 165, type: 'norm', desc: 'Galaxy #165' },
  'Uagerosat': { num: 166, type: 'norm', desc: 'Galaxy #166' },
  'Impoxectin': { num: 167, type: 'norm', desc: 'Galaxy #167' },
  'Twoodmand': { num: 168, type: 'norm', desc: 'Galaxy #168' },
  'Hilfsesorbs': { num: 169, type: 'norm', desc: 'Galaxy #169' },
  'Ezdaranit': { num: 170, type: 'norm', desc: 'Galaxy #170' },
  'Wiensanshe': { num: 171, type: 'norm', desc: 'Galaxy #171' },
  'Ewheelonc': { num: 172, type: 'norm', desc: 'Galaxy #172' },
  'Litzmantufa': { num: 173, type: 'norm', desc: 'Galaxy #173' },
  'Emarmatosi': { num: 174, type: 'norm', desc: 'Galaxy #174' },
  'Mufimbomacvi': { num: 175, type: 'norm', desc: 'Galaxy #175' },
  'Wongquarum': { num: 176, type: 'norm', desc: 'Galaxy #176' },
  'Hapirajua': { num: 177, type: 'norm', desc: 'Galaxy #177' },
  'Igbinduina': { num: 178, type: 'norm', desc: 'Galaxy #178' },
  'Wepaitvas': { num: 179, type: 'norm', desc: 'Galaxy #179' },
  'Sthatigudi': { num: 180, type: 'norm', desc: 'Galaxy #180' },
  'Yekathsebehn': { num: 181, type: 'norm', desc: 'Galaxy #181' },
  'Ebedeagurst': { num: 182, type: 'norm', desc: 'Galaxy #182' },
  'Nolisonia': { num: 183, type: 'norm', desc: 'Galaxy #183' },
  'Ulexovitab': { num: 184, type: 'norm', desc: 'Galaxy #184' },
  'Iodhinxois': { num: 185, type: 'norm', desc: 'Galaxy #185' },
  'Irroswitzs': { num: 186, type: 'norm', desc: 'Galaxy #186' },
  'Bifredait': { num: 187, type: 'norm', desc: 'Galaxy #187' },
  'Beiraghedwe': { num: 188, type: 'norm', desc: 'Galaxy #188' },
  'Yeonatlak': { num: 189, type: 'norm', desc: 'Galaxy #189' },
  'Cugnatachh': { num: 190, type: 'norm', desc: 'Galaxy #190' },
  'Nozoryenki': { num: 191, type: 'norm', desc: 'Galaxy #191' },
  'Ebralduri': { num: 192, type: 'norm', desc: 'Galaxy #192' },
  'Evcickcandj': { num: 193, type: 'norm', desc: 'Galaxy #193' },
  'Ziybosswin': { num: 194, type: 'norm', desc: 'Galaxy #194' },
  'Heperclait': { num: 195, type: 'norm', desc: 'Galaxy #195' },
  'Sugiuniam': { num: 196, type: 'norm', desc: 'Galaxy #196' },
  'Aaseertush': { num: 197, type: 'norm', desc: 'Galaxy #197' },
  'Uglyestemaa': { num: 198, type: 'norm', desc: 'Galaxy #198' },
  'Horeroedsh': { num: 199, type: 'norm', desc: 'Galaxy #199' },
  'Drundemiso': { num: 200, type: 'norm', desc: 'Galaxy #200' },
  'Ityanianat': { num: 201, type: 'norm', desc: 'Galaxy #201' },
  'Purneyrine': { num: 202, type: 'norm', desc: 'Galaxy #202' },
  'Dokiessmat': { num: 203, type: 'norm', desc: 'Galaxy #203' },
  'Nupiacheh': { num: 204, type: 'norm', desc: 'Galaxy #204' },
  'Dihewsonj': { num: 205, type: 'norm', desc: 'Galaxy #205' },
  'Rudrailhik': { num: 206, type: 'norm', desc: 'Galaxy #206' },
  'Tweretnort': { num: 207, type: 'norm', desc: 'Galaxy #207' },
  'Snatreetze': { num: 208, type: 'norm', desc: 'Galaxy #208' },
  'Iwundaracos': { num: 209, type: 'norm', desc: 'Galaxy #209' },
  'Digarlewena': { num: 210, type: 'norm', desc: 'Galaxy #210' },
  'Erquagsta': { num: 211, type: 'norm', desc: 'Galaxy #211' },
  'Logovoloin': { num: 212, type: 'norm', desc: 'Galaxy #212' },
  'Boyaghosganh': { num: 213, type: 'norm', desc: 'Galaxy #213' },
  'Kuolungau': { num: 214, type: 'norm', desc: 'Galaxy #214' },
  'Pehneldept': { num: 215, type: 'norm', desc: 'Galaxy #215' },
  'Yevettiiqidcon': { num: 216, type: 'norm', desc: 'Galaxy #216' },
  'Sahliacabru': { num: 217, type: 'norm', desc: 'Galaxy #217' },
  'Noggalterpor': { num: 218, type: 'norm', desc: 'Galaxy #218' },
  'Chmageaki': { num: 219, type: 'norm', desc: 'Galaxy #219' },
  'Veticueca': { num: 220, type: 'norm', desc: 'Galaxy #220' },
  'Vittesbursul': { num: 221, type: 'norm', desc: 'Galaxy #221' },
  'Nootanore': { num: 222, type: 'norm', desc: 'Galaxy #222' },
  'Innebdjerah': { num: 223, type: 'norm', desc: 'Galaxy #223' },
  'Kisvarcini': { num: 224, type: 'norm', desc: 'Galaxy #224' },
  'Cuzcogipper': { num: 225, type: 'norm', desc: 'Galaxy #225' },
  'Pamanhermonsu': { num: 226, type: 'norm', desc: 'Galaxy #226' },
  'Brotoghek': { num: 227, type: 'norm', desc: 'Galaxy #227' },
  'Mibittara': { num: 228, type: 'norm', desc: 'Galaxy #228' },
  'Huruahili': { num: 229, type: 'norm', desc: 'Galaxy #229' },
  'Raldwicarn': { num: 230, type: 'norm', desc: 'Galaxy #230' },
  'Ezdartlic': { num: 231, type: 'norm', desc: 'Galaxy #231' },
  'Badesclema': { num: 232, type: 'norm', desc: 'Galaxy #232' },
  'Isenkeyan': { num: 233, type: 'norm', desc: 'Galaxy #233' },
  'Iadoitesu': { num: 234, type: 'norm', desc: 'Galaxy #234' },
  'Yagrovoisi': { num: 235, type: 'norm', desc: 'Galaxy #235' },
  'Ewcomechio': { num: 236, type: 'norm', desc: 'Galaxy #236' },
  'Inunnunnoda': { num: 237, type: 'norm', desc: 'Galaxy #237' },
  'Dischiutun': { num: 238, type: 'norm', desc: 'Galaxy #238' },
  'Yuwarugha': { num: 239, type: 'norm', desc: 'Galaxy #239' },
  'Ialmendra': { num: 240, type: 'norm', desc: 'Galaxy #240' },
  'Reponudrle': { num: 241, type: 'norm', desc: 'Galaxy #241' },
  'Rinjanagrbo': { num: 242, type: 'norm', desc: 'Galaxy #242' },
  'Zeziceloh': { num: 243, type: 'norm', desc: 'Galaxy #243' },
  'Oeileutasc': { num: 244, type: 'norm', desc: 'Galaxy #244' },
  'Zicniijinis': { num: 245, type: 'norm', desc: 'Galaxy #245' },
  'Dugnowarilda': { num: 246, type: 'norm', desc: 'Galaxy #246' },
  'Neuxoisan': { num: 247, type: 'norm', desc: 'Galaxy #247' },
  'Ilmenhorn': { num: 248, type: 'norm', desc: 'Galaxy #248' },
  'Rukwatsuku': { num: 249, type: 'norm', desc: 'Galaxy #249' },
  'Nepitzaspru': { num: 250, type: 'norm', desc: 'Galaxy #250' },
  'Chcehoemig': { num: 251, type: 'norm', desc: 'Galaxy #251' },
  'Haffneyrin': { num: 252, type: 'norm', desc: 'Galaxy #252' },
  'Uliciawai': { num: 253, type: 'norm', desc: 'Galaxy #253' },
  'Tuhgrespod': { num: 254, type: 'norm', desc: 'Galaxy #254' },
  'Iousongola': { num: 255, type: 'norm', desc: 'Galaxy #255' },
  'Odyalutai': { num: 256, type: 'norm', desc: 'Galaxy #256 - Final galaxy' },
}

// Galaxy type colors and labels
const GALAXY_TYPES = {
  'lush': {
    label: 'Lush',
    color: 'from-emerald-600 to-green-700',
    border: 'border-emerald-500',
    badge: 'bg-emerald-500 text-white',
    icon: '🌿'
  },
  'harsh': {
    label: 'Harsh',
    color: 'from-red-600 to-orange-700',
    border: 'border-red-500',
    badge: 'bg-red-500 text-white',
    icon: '⚔️'
  },
  'norm': {
    label: 'Normal',
    color: 'from-cyan-600 to-blue-700',
    border: 'border-cyan-500',
    badge: 'bg-cyan-500 text-white',
    icon: '🌌'
  },
  'empty': {
    label: 'Empty',
    color: 'from-gray-600 to-gray-700',
    border: 'border-gray-500',
    badge: 'bg-gray-500 text-white',
    icon: '🌑'
  }
}

/**
 * Level 2 Hierarchy: Galaxy Grid
 *
 * Shows a grid of galaxies within the selected reality.
 * Each galaxy card shows system count and region count.
 * Galaxies are sorted by their canonical number.
 */
export default function GalaxyGrid({ reality, onSelect, selectedGalaxy }) {
  const [galaxies, setGalaxies] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (reality) {
      loadGalaxies()
    }
  }, [reality])

  async function loadGalaxies() {
    setLoading(true)
    setError(null)
    try {
      const res = await axios.get(`/api/galaxies/summary?reality=${encodeURIComponent(reality)}`)
      setGalaxies(res.data.galaxies || [])
    } catch (err) {
      console.error('Failed to load galaxies:', err)
      setError('Failed to load galaxy data')
      setGalaxies([])
    } finally {
      setLoading(false)
    }
  }

  // Sort galaxies by their canonical number
  const sortedGalaxies = useMemo(() => {
    return [...galaxies].sort((a, b) => {
      const numA = ALL_GALAXIES[a.galaxy]?.num || 999
      const numB = ALL_GALAXIES[b.galaxy]?.num || 999
      return numA - numB
    })
  }, [galaxies])

  // Get galaxy metadata with fallback
  function getGalaxyMeta(name) {
    return ALL_GALAXIES[name] || { num: '?', type: 'norm', desc: 'Uncharted galaxy' }
  }

  if (loading) {
    return (
      <Card>
        <div className="text-center py-8 text-gray-400">
          <ArrowPathIcon className="w-6 h-6 animate-spin mx-auto mb-2" />
          Loading galaxies for {reality}...
        </div>
      </Card>
    )
  }

  if (error) {
    return (
      <Card>
        <div className="text-center py-8">
          <p className="text-red-400 mb-4">{error}</p>
          <button
            onClick={loadGalaxies}
            className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded text-white"
          >
            Retry
          </button>
        </div>
      </Card>
    )
  }

  if (galaxies.length === 0) {
    return (
      <Card>
        <div className="text-center py-8 text-gray-400">
          <SparklesIcon className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>No galaxies found in {reality} mode.</p>
          <p className="text-sm mt-2">Systems need to be added to see galaxies here.</p>
        </div>
      </Card>
    )
  }

  // Total counts
  const totalSystems = sortedGalaxies.reduce((sum, g) => sum + g.system_count, 0)
  const totalRegions = sortedGalaxies.reduce((sum, g) => sum + g.region_count, 0)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <GlobeAltIcon className="w-6 h-6 text-cyan-400" />
            Galaxies in {reality}
          </h2>
          <p className="text-sm text-gray-400 mt-1">
            {sortedGalaxies.length} galaxies with data • {totalSystems.toLocaleString()} systems • {totalRegions.toLocaleString()} regions
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {sortedGalaxies.map((g) => {
          const meta = getGalaxyMeta(g.galaxy)
          const typeInfo = GALAXY_TYPES[meta.type] || GALAXY_TYPES.norm
          const isSelected = selectedGalaxy === g.galaxy

          return (
            <button
              key={g.galaxy}
              onClick={() => onSelect(g.galaxy)}
              className={`
                relative overflow-hidden rounded-xl transition-all duration-300
                text-left group
                ${isSelected
                  ? `ring-2 ring-cyan-400 ring-offset-2 ring-offset-gray-900 scale-[1.02]`
                  : `hover:scale-[1.02] hover:shadow-lg hover:shadow-cyan-500/10`
                }
              `}
            >
              {/* Gradient background */}
              <div className={`
                absolute inset-0 bg-gradient-to-br opacity-90
                ${isSelected ? 'from-cyan-600 to-blue-700' : `${typeInfo.color}`}
              `} />

              {/* Subtle pattern overlay */}
              <div className="absolute inset-0 opacity-10" style={{
                backgroundImage: 'radial-gradient(circle at 2px 2px, white 1px, transparent 0)',
                backgroundSize: '16px 16px'
              }} />

              {/* Content */}
              <div className="relative p-4">
                {/* Header with number badge */}
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <span className={`
                      w-8 h-8 rounded-lg flex items-center justify-center text-sm font-bold
                      ${isSelected ? 'bg-white/30 text-white' : 'bg-black/30 text-white'}
                    `}>
                      {meta.num}
                    </span>
                    <span className={`
                      text-xs px-2 py-0.5 rounded-full font-medium
                      ${isSelected ? 'bg-white/20 text-white' : typeInfo.badge}
                    `}>
                      {typeInfo.label}
                    </span>
                  </div>
                  {isSelected && (
                    <span className="bg-white text-cyan-600 text-xs font-bold px-2 py-1 rounded-full shadow">
                      Selected
                    </span>
                  )}
                </div>

                {/* Galaxy name */}
                <h3 className="font-bold text-lg text-white truncate mb-1">
                  {g.galaxy}
                </h3>

                {/* Description */}
                <p className="text-xs text-white/70 mb-4 line-clamp-2 min-h-[2rem]">
                  {meta.desc}
                </p>

                {/* Stats row */}
                <div className="flex items-center justify-between pt-3 border-t border-white/20">
                  <div className="text-center">
                    <div className="text-xl font-bold text-white">
                      {g.system_count.toLocaleString()}
                    </div>
                    <div className="text-xs text-white/60 uppercase tracking-wide">
                      Systems
                    </div>
                  </div>
                  <div className="w-px h-8 bg-white/20" />
                  <div className="text-center">
                    <div className="text-xl font-bold text-white">
                      {g.region_count}
                    </div>
                    <div className="text-xs text-white/60 uppercase tracking-wide">
                      Regions
                    </div>
                  </div>
                </div>
              </div>

              {/* Hover glow effect */}
              <div className={`
                absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300
                bg-gradient-to-t from-cyan-500/20 to-transparent pointer-events-none
              `} />
            </button>
          )
        })}
      </div>
    </div>
  )
}
