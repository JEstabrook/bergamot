# Title     : Generate TCGA ENSEMBL regulons
# Objective : Convert ENTREZID labeled VIPER regulons to ENSEMBL
# Created by: Joey Estabrook
# Created on: 9/21/17


suppressWarnings(suppressMessages(require("AnnotationDbi")))
suppressWarnings(suppressMessages(require("org.Hs.eg.db")))
suppressWarnings(suppressMessages(require("data.table")))

getMatrixWithSelectedIds = function(df, columns=list('Regulator','Target'), db='org.Hs.eg.db', type='ENSEMBL', keytype='ENTREZID'){
    df2 = df
    for (column in columns){
        stopifnot( inherits( get(db), "AnnotationDb" ) )
        df2[[column]] = suppressWarnings(mapIds(get(db), keys=as.character(df[[column]]),column=type, keytype=keytype, multiVals='first'))
    }
    return(df2)
}

basedir <- "."
datadir <- paste(basedir,"data/", sep="/")

main = function(){
    setwd(datadir)
    args = commandArgs(trailingOnly = TRUE)
    cohort = (args[1])
    cohort_table = fread(paste('tmp-', cohort,'.adj',sep=''))
    mappedIDs = getMatrixWithSelectedIds(cohort_table)
    write.table(mappedIDs,paste('tmp-ensembl-',cohort,'.adj',sep=''),sep='\t',row.names=F,quote=F)
}

main()
