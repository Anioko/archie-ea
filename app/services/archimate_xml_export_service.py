"""SA-005: ArchiMate OEF XML export service (app/services façade).

Produces valid ArchiMate Open Exchange Format (OEF) XML importable by
Archi and Sparx EA.
"""

import xml.etree.ElementTree as ET

_OEF_NS = "http://www.opengroup.org/xsd/archimate/3.0/"
_XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"


class ArchiMateXMLExportService:
    """Generates OEF-compliant ArchiMate XML from element/relationship lists."""

    def export_to_xml(self, elements, relationships):
        """Produce valid OEF XML for Archi/Sparx import.

        Args:
            elements: iterable of ArchiMate element objects (or dicts).
            relationships: iterable of ArchiMate relationship objects (or dicts).

        Returns:
            str: OEF XML string (no XML declaration — caller may prepend).
        """
        root = ET.Element('model', {
            'xmlns': _OEF_NS,
            'xmlns:xsi': _XSI_NS,
        })

        elements_el = ET.SubElement(root, 'elements')
        for elem in (elements or []):
            e = ET.SubElement(elements_el, 'element')
            e.set('identifier', str(_attr(elem, 'id', '')))
            e.set('xsi:type', _attr(elem, 'element_type', 'ApplicationComponent'))
            name_el = ET.SubElement(e, 'name')
            name_el.text = _attr(elem, 'name', '')
            doc = _attr(elem, 'documentation', '') or _attr(elem, 'description', '')
            if doc:
                doc_el = ET.SubElement(e, 'documentation')
                doc_el.text = doc

        relationships_el = ET.SubElement(root, 'relationships')
        for rel in (relationships or []):
            r = ET.SubElement(relationships_el, 'relationship')
            r.set('identifier', str(_attr(rel, 'id', '')))
            r.set('source', str(_attr(rel, 'source_id', '')))
            r.set('target', str(_attr(rel, 'target_id', '')))
            r.set('xsi:type', _attr(rel, 'relationship_type', 'Association'))

        return ET.tostring(root, encoding='unicode', xml_declaration=False)


def _attr(obj, key, default=''):
    """Return obj[key] (dict) or obj.key (object) with fallback."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def export_to_xml(elements=None, relationships=None, **kwargs):
    """Module-level convenience wrapper around ArchiMateXMLExportService."""
    svc = ArchiMateXMLExportService()
    return svc.export_to_xml(elements or [], relationships or [])
