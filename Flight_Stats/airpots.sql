CREATE 
    ALGORITHM = UNDEFINED 
    DEFINER = `root`@`%` 
    SQL SECURITY DEFINER
VIEW `flights`.`airports` AS
    SELECT DISTINCT
        `A`.`airport` AS `airport`,
        `A`.`state` AS `state`,
        `A`.`state_name` AS `state_name`
    FROM
        (SELECT 
            `flights`.`raw_market`.`Origin` AS `airport`,
                `flights`.`raw_market`.`OriginState` AS `state`,
                `flights`.`raw_market`.`OriginStateName` AS `state_name`
        FROM
            `flights`.`raw_market` UNION ALL SELECT 
            `flights`.`raw_market`.`Dest` AS `airport`,
                `flights`.`raw_market`.`DestState` AS `state`,
                `flights`.`raw_market`.`DestStateName` AS `state_name`
        FROM
            `flights`.`raw_market`) `A`
    ORDER BY `A`.`airport`
