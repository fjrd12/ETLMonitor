<?xml version="1.0" encoding="UTF-8"?>
<!--
  Toy-demo default: passes CONTENT.xml through unchanged, wrapped in a
  <Monetized> envelope so downstream steps can see the transform ran.
  Real deployments replace this per-MESTYP with actual valuation rules
  (e.g. PROJECT02.xslt, MATMAS.xslt) that compute Amount/Currency from
  the IDoc payload; monetizer.json is the dispatch table that picks
  which one runs for a given MESTYP.
-->
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <xsl:output method="xml" indent="yes"/>

  <xsl:template match="/">
    <Monetized>
      <xsl:copy-of select="."/>
    </Monetized>
  </xsl:template>
</xsl:stylesheet>
