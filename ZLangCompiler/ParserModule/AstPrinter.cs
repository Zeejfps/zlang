using ParserModule.Nodes;

namespace ParserModule;

public sealed class AstPrinter : IAstNodeVisitor
{
    public void VisitIntegerNumberExpression(LiteralIntegerExpression integerNumberExpression)
    {
    }
}