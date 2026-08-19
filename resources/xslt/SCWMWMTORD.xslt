<xsl:key name="qty-unit" match="_SCWM-E1LTORI" use="normalize-space(MEINS)"/>
  <xsl:template match="/">
    <xsl:variable name="idoc" select="(//*[local-name()='IDOC'])[1]"/>
    <xsl:variable name="control" select="$idoc/*[local-name()='EDI_DC40'][1]"/>
    <xsl:variable name="mestyp" select="normalize-space($control/*[local-name()='MESTYP'])"/>
    <xsl:variable name="idoctyp" select="normalize-space($control/*[local-name()='IDOCTYP'])"/>
    <xsl:choose>
      <xsl:when test="$mestyp='/SCWM/WMTORD' and $idoctyp='/SCWM/WMTOID01'">
        <xsl:variable name="tasks" select="$idoc//*[local-name()='_SCWM-E1LTORI']"/>
        <IDOC_VALUATION>
          <DOCNUM><xsl:value-of select="$control/*[local-name()='DOCNUM']"/></DOCNUM>
          <MESTYP>/SCWM/WMTORD</MESTYP>
          <IDOCTYP>/SCWM/WMTOID01</IDOCTYP>
          <VALUATIONS>
            <xsl:for-each select="$tasks[
              normalize-space(*[local-name()='MEINS'])!='' and
              generate-id()=generate-id(key('qty-unit',normalize-space(*[local-name()='MEINS']))[1])]">
              <xsl:variable name="u" select="normalize-space(*[local-name()='MEINS'])"/>
              <VALUATION>
                <xsl:attribute name="primary"><xsl:choose><xsl:when test="position()=1">true</xsl:when><xsl:otherwise>false</xsl:otherwise></xsl:choose></xsl:attribute>
                <TYPE>QUANTITY</TYPE>
                <VALUE><xsl:value-of select="format-number(sum(key('qty-unit',$u)/*[local-name()='VSOLM']),'0.##########')"/></VALUE>
                <UNIT><xsl:value-of select="$u"/></UNIT>
                <SOURCE>_SCWM-E1LTORI/VSOLM + MEINS</SOURCE>
                <STATUS>VALUATED</STATUS>
              </VALUATION>
            </xsl:for-each>
            <VALUATION primary="false">
              <TYPE>OBJECT_COUNT</TYPE>
              <VALUE><xsl:value-of select="count($tasks)"/></VALUE>
              <UNIT>WAREHOUSE_TASK</UNIT>
              <SOURCE>count(_SCWM-E1LTORI)</SOURCE>
              <STATUS>VALUATED</STATUS>
            </VALUATION>
            <xsl:for-each select="$idoc//*[local-name()='_SCWM-E1LTORH']
              [normalize-space(*[local-name()='PLANDURA'])!='' and number(*[local-name()='PLANDURA']) &gt; 0]">
              <VALUATION primary="false">
                <TYPE>TIME</TYPE>
                <VALUE><xsl:value-of select="normalize-space(*[local-name()='PLANDURA'])"/></VALUE>
                <UNIT><xsl:value-of select="normalize-space(*[local-name()='UNIT_T'])"/></UNIT>
                <SOURCE>_SCWM-E1LTORH/PLANDURA + UNIT_T</SOURCE>
                <STATUS>VALUATED</STATUS>
              </VALUATION>
            </xsl:for-each>
          </VALUATIONS>
        </IDOC_VALUATION>
      </xsl:when>
      <xsl:otherwise>
        <IDOC_VALUATION><STATUS>UNSUPPORTED_MESTYP_OR_IDOCTYP</STATUS><EXPECTED>/SCWM/WMTORD / /SCWM/WMTOID01</EXPECTED></IDOC_VALUATION>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>