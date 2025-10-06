using ParserModule.Nodes;

namespace ParserModule;

public interface IAstNodeVisitor
{
    void VisitIntegerNumberExpression(LiteralIntegerExpression integerNumberExpression);
}