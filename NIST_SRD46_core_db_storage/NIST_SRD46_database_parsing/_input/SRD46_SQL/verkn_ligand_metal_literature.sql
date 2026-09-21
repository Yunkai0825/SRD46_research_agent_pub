-- MySQL dump 10.13  Distrib 5.1.49, for debian-linux-gnu (x86_64)
--
-- Host: localhost    Database: stability
-- ------------------------------------------------------
-- Server version	5.1.49-3

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `verkn_ligand_metal_literature`
--

DROP TABLE IF EXISTS `verkn_ligand_metal_literature`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `verkn_ligand_metal_literature` (
  `verkn_ligand_metal_literatureID` int(11) NOT NULL AUTO_INCREMENT,
  `ligandenNr` int(11) NOT NULL DEFAULT '0',
  `metalNr` int(11) DEFAULT '0',
  `literatureNr` int(11) NOT NULL DEFAULT '0',
  `literature_altNr` int(11) DEFAULT '0',
  `not_used` int(4) DEFAULT NULL,
  `comment` varchar(255) DEFAULT NULL,
  `Acc_feld` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`verkn_ligand_metal_literatureID`),
  KEY `ligandenNr` (`ligandenNr`),
  KEY `metalNr` (`metalNr`),
  KEY `literatureNr` (`literatureNr`),
  KEY `literature_altNr` (`literature_altNr`)
) ENGINE=MyISAM AUTO_INCREMENT=79969 DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;

/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2011-08-30 17:01:06
